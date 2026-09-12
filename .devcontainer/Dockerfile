# Builds the managed non-root development identity expected by Dioikeo.
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm@sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39

ARG CODEX_VERSION=0.154.0
ARG WORKSPACE_USER
ARG WORKSPACE_HOME
ARG WORKSPACE_FOLDER

USER root

RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends cron jq ripgrep vim \
    && rm -rf /var/lib/apt/lists/*

RUN printf '%s\n' "$WORKSPACE_USER" | grep -Eq '^[a-z_][a-z0-9_-]{0,31}$' \
    && [ "$WORKSPACE_USER" != vscode ] \
    && [ "$WORKSPACE_HOME" = "/home/$WORKSPACE_USER" ] \
    && case "$WORKSPACE_FOLDER" in "$WORKSPACE_HOME"/*) ;; *) exit 1 ;; esac \
    && usermod --login "$WORKSPACE_USER" --home "$WORKSPACE_HOME" --move-home vscode \
    && groupmod --new-name "$WORKSPACE_USER" vscode \
    && sed -i "s/^vscode /$WORKSPACE_USER /" /etc/sudoers.d/vscode \
    && mv /etc/sudoers.d/vscode "/etc/sudoers.d/$WORKSPACE_USER" \
    && visudo -cf "/etc/sudoers.d/$WORKSPACE_USER" \
    && install -d -m 0755 -o "$WORKSPACE_USER" -g "$WORKSPACE_USER" "$WORKSPACE_FOLDER" \
    && install -d -m 0700 -o "$WORKSPACE_USER" -g "$WORKSPACE_USER" \
       "$WORKSPACE_HOME/.codex"

USER ${WORKSPACE_USER}

RUN curl -fsSL https://chatgpt.com/codex/install.sh -o /tmp/codex-install.sh \
    && CODEX_RELEASE="$CODEX_VERSION" CODEX_NON_INTERACTIVE=1 \
       sh /tmp/codex-install.sh \
    && rm -f /tmp/codex-install.sh

ENV HOME="${WORKSPACE_HOME}"
ENV PATH="${WORKSPACE_HOME}/.local/bin:${PATH}"
ENV SHELL="/bin/bash"

WORKDIR ${WORKSPACE_FOLDER}
