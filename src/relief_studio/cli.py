"""CLI generation and local server entrypoint using the shared geometry pipeline."""

import argparse
import json
import sys
from importlib.resources import files
from pathlib import Path

from pydantic import ValidationError

from .exports import export_project
from .geometry import build_project
from .settings import Settings


def sample_bytes() -> bytes:
    return files("relief_studio").joinpath("assets/alpine.svg").read_bytes()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="relief", description="Turn images into printable two-color reliefs."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser(
        "generate", help="Export an image (or built-in sample) as a print pack"
    )
    generate.add_argument("image", nargs="?", type=Path)
    generate.add_argument("--output", "-o", type=Path, required=True)
    generate.add_argument("--settings", type=Path)
    for name in ("width", "height", "base", "relief", "clearance", "bed-width", "bed-height"):
        generate.add_argument(f"--{name}", type=float)
    generate.add_argument("--layout", choices=["plaque", "tiles", "puzzle"])
    generate.add_argument("--hanging", choices=["none", "loops", "keyholes"])
    generate.add_argument("--columns", type=int)
    generate.add_argument("--rows", type=int)
    generate.add_argument("--threshold", type=int)
    generate.add_argument("--invert", action="store_true", default=None)
    generate.add_argument("--no-frame", action="store_true")
    serve = commands.add_parser("serve", help="Start the local browser workbench")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--output-root", type=Path, default=Path("output/projects"))
    arguments = parser.parse_args()
    if arguments.command == "serve":
        import uvicorn

        from .server import create_app

        uvicorn.run(create_app(arguments.output_root), host=arguments.host, port=arguments.port)
        return
    try:
        config = json.loads(arguments.settings.read_text()) if arguments.settings else {}
        for name in ("width", "height", "base", "relief", "clearance", "bed_width", "bed_height"):
            value = getattr(arguments, name)
            if value is not None:
                config[name + "_mm"] = value
        for name in ("layout", "hanging", "columns", "rows", "threshold", "invert"):
            value = getattr(arguments, name)
            if value is not None:
                config[name] = value
        if arguments.no_frame:
            config["frame"] = False
        settings = Settings.model_validate(config)
        data = arguments.image.read_bytes() if arguments.image else sample_bytes()
        manifest = export_project(build_project(data, settings), arguments.output, data)
        print(f"Exported {manifest['piece_count']} piece(s) to {arguments.output.resolve()}")
        print("Open PRINTING.md before slicing. Physical fit has not been tested.")
    except (OSError, ValueError, ValidationError) as exc:
        print(f"relief: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
