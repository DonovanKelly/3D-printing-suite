"""Local API serving the shared geometry pipeline and bundled browser workbench.

Preview computation is serialized and retained in a four-entry memory cache.
Only explicit export writes a durable print pack. Upload bodies are bounded
before multipart parsing; file routes serve generated artifacts, never inputs.
The service is for trusted local use, with no remote authentication layer.
An explicitly configured public origin supports local proxies that rewrite Host;
forwarding headers alone never authorize another browser origin.
"""

import logging
from collections import OrderedDict
from importlib.resources import files
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from .artwork import MAX_INPUT_BYTES
from .cli import sample_bytes
from .exports import export_project, project_manifest, vector_svg
from .geometry import build_project
from .settings import Settings

logger = logging.getLogger(__name__)


def create_app(output_root: Path | None = None, public_origin: str | None = None) -> FastAPI:
    if public_origin is not None:
        parsed = urlparse(public_origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Public origin must be an HTTP(S) origin without credentials or a path."
            )
        public_origin = f"{parsed.scheme}://{parsed.netloc}"
    app = FastAPI(title="Relief Studio", version="0.1.0")
    root = (output_root or Path("output/projects")).resolve()
    lock = Lock()
    previews = OrderedDict()

    @app.middleware("http")
    async def local_request_boundary(request: Request, call_next):
        if request.method == "POST":
            origin = request.headers.get("origin")
            if (
                origin
                and origin != public_origin
                and urlparse(origin).hostname != request.url.hostname
            ):
                return JSONResponse({"detail": "Cross-origin generation is not allowed."}, 403)
            # Bounded pre-read avoids spilling arbitrary upload bodies to multipart temp files.
            chunks, length = [], 0
            async for chunk in request.stream():
                length += len(chunk)
                if length > MAX_INPUT_BYTES + 64 * 1024:
                    return JSONResponse({"detail": "Upload exceeds the 12 MiB limit."}, 413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "0.1.0", "processing": "local"}

    @app.get("/api/defaults")
    def defaults():
        return Settings().model_dump()

    @app.get("/api/sample")
    def sample():
        return Response(sample_bytes(), media_type="image/svg+xml")

    @app.post("/api/preview")
    async def preview(request: Request):
        if not lock.acquire(blocking=False):
            raise HTTPException(409, "Another preview is building. Try again in a moment.")
        try:
            async with request.form(
                max_files=1, max_fields=1, max_part_size=MAX_INPUT_BYTES
            ) as form:
                config = form.get("settings", "{}")
                if not isinstance(config, str):
                    raise ValueError("Settings must be a JSON object.")
                settings = Settings.model_validate_json(config)
                upload = form.get("image")
                data = (
                    await upload.read(MAX_INPUT_BYTES + 1)
                    if isinstance(upload, UploadFile)
                    else sample_bytes()
                )
            project = await run_in_threadpool(build_project, data, settings)
            identifier = str(uuid4())
            previews[identifier] = (project, data)
            while len(previews) > 4:
                previews.popitem(last=False)
            meshes = []
            for piece in project.pieces:
                for name, mesh in (("background", piece.base), ("artwork", piece.artwork)):
                    if mesh is not None:
                        meshes.append(
                            {
                                "piece": piece.tile.name,
                                "material": name,
                                "origin": piece.origin,
                                "vertices": mesh.vertices.round(5).ravel().tolist(),
                                "faces": mesh.faces.ravel().tolist(),
                            }
                        )
            return {
                "id": identifier,
                "manifest": project_manifest(project),
                "meshes": meshes,
                "vector_svg": vector_svg(project),
                "assembly_svg": vector_svg(project, True),
            }
        except ValidationError as exc:
            raise HTTPException(422, "; ".join(error["msg"] for error in exc.errors())) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Preview generation failed")
            raise HTTPException(
                500, "Could not build this geometry. Try a simpler image or layout."
            ) from exc
        finally:
            lock.release()

    @app.post("/api/export/{identifier}")
    async def export(identifier: UUID):
        key = str(identifier)
        cached = previews.get(key)
        if cached is None:
            raise HTTPException(410, "This preview expired. Rebuild it before exporting.")
        if not lock.acquire(blocking=False):
            raise HTTPException(
                409, "Another operation is running. Try exporting again in a moment."
            )
        try:
            destination = root / key
            if not (destination / "print-pack.zip").is_file():
                project, data = cached
                await run_in_threadpool(export_project, project, destination, data)
            return {"download_url": f"/api/files/{key}/print-pack.zip"}
        except Exception as exc:
            logger.exception("Export failed")
            raise HTTPException(
                500, "Could not save the print pack. Check available disk space."
            ) from exc
        finally:
            lock.release()

    @app.get("/api/files/{identifier}/{filename}")
    def download(identifier: UUID, filename: str):
        if filename not in {"print-pack.zip", "preview.png", "assembly.svg", "project.json"}:
            raise HTTPException(404)
        path = root / str(identifier) / filename
        if not path.is_file():
            raise HTTPException(404)
        return FileResponse(path, filename=filename)

    static = Path(str(files("relief_studio").joinpath("static")))
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="workbench")
    else:

        @app.get("/")
        def missing_build():
            return JSONResponse(
                {"detail": "Build the workbench with npm --prefix web run build."}, 503
            )

    return app
