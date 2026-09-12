#!/usr/bin/env bash

# Supervise this checkout's local preview and rebuild its frontend on source edits.
# Keep process state outside Git and print exports in the shared workspace folder.
set -euo pipefail
umask 077

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_key="$(printf '%s' "$repo_root" | sha256sum | cut -c1-10)"
state_dir="$HOME/.local/state/relief-preview-$repo_key"
config="$state_dir/supervisor.conf"
port="${RELIEF_PREVIEW_PORT:-8000}"
output_root="${RELIEF_OUTPUT_ROOT:-$repo_root/output/projects}"
if [[ -z "${RELIEF_OUTPUT_ROOT:-}" && -d /shared && -w /shared ]]; then
  output_root=/shared/relief-studio/projects
fi

cd "$repo_root"
install -d -m 700 "$state_dir"
exec 9>"$state_dir/control.lock"
flock -w 30 9

control() { supervisorctl -c "$config" "$@"; }
running() { [[ -f "$config" ]] && control pid >/dev/null 2>&1; }

stop() {
  if running; then
    control shutdown
    # Shutdown acknowledges before children and the control socket are gone.
    # Wait for cleanup so an immediate start cannot race the old daemon.
    for _ in {1..30}; do
      if [[ ! -e "$state_dir/supervisor.pid" && ! -S "$state_dir/control.sock" ]]; then
        return
      fi
      sleep 1
    done
    printf 'Preview shutdown has not completed; inspect %s\n' "$state_dir" >&2
    return 1
  fi
}

start() {
  command -v supervisord >/dev/null
  [[ -x .venv/bin/relief && -f src/relief_studio/static/index.html ]] || {
    printf 'Run bash scripts/workspace-preview.sh setup first.\n' >&2
    return 1
  }
  if ! running; then
    cat >"$config" <<EOF
[unix_http_server]
file=$state_dir/control.sock
chmod=0600

[supervisord]
umask=0077
logfile=$state_dir/supervisor.log
logfile_maxbytes=1MB
logfile_backups=2
pidfile=$state_dir/supervisor.pid
childlogdir=$state_dir

[rpcinterface:supervisor]
supervisor.rpcinterface_factory=supervisor.rpcinterface:make_main_rpcinterface

[supervisorctl]
serverurl=unix://$state_dir/control.sock

[program:relief]
directory=$repo_root
command="$repo_root/.venv/bin/relief" serve --host 0.0.0.0 --port $port --output-root "$output_root"
autostart=true
autorestart=true
startsecs=2
stopasgroup=true
killasgroup=true
redirect_stderr=true
stdout_logfile=$state_dir/relief.log
stdout_logfile_maxbytes=2MB
stdout_logfile_backups=2

[program:frontend]
directory=$repo_root/web
command=npm run build -- --watch
autostart=true
autorestart=true
startsecs=2
stopasgroup=true
killasgroup=true
redirect_stderr=true
stdout_logfile=$state_dir/frontend.log
stdout_logfile_maxbytes=2MB
stdout_logfile_backups=2
EOF
    # Close the controller lock in the daemon so later stop/start calls can run.
    supervisord -c "$config" 9>&-
  else
    control start all >/dev/null
  fi
  for _ in {1..30}; do
    if control status | awk '$2 != "RUNNING" { bad=1 } END { exit bad }' &&
       curl --fail --silent --max-time 2 "http://127.0.0.1:$port/api/health" >/dev/null; then
      printf 'Preview ready on port %s; exports: %s\n' "$port" "$output_root"
      return
    fi
    sleep 1
  done
  control status >&2 || true
  printf 'Preview failed; inspect logs in %s\n' "$state_dir" >&2
  return 1
}

case "${1:-start}" in
  setup)
    python3 -m venv .venv
    .venv/bin/pip install -r requirements-dev.lock
    .venv/bin/pip install -e . --no-deps
    npm --prefix web ci
    npm --prefix web run build
    ;;
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) control status ;;
  *) printf 'Usage: %s {setup|start|stop|restart|status}\n' "$0" >&2; exit 2 ;;
esac
