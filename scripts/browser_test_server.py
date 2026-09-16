"""Run an isolated browser-test API; its exports are discarded when this process exits."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn

from relief_studio.server import create_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("port", type=int)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="relief-browser-tests-") as folder:
        uvicorn.run(create_app(Path(folder)), host="127.0.0.1", port=args.port, log_level="warning")
