"""Verify local upload, preview, durable export, and download boundaries end to end."""

import io
import json
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from relief_studio.cli import sample_bytes
from relief_studio.server import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "exports"))


def test_upload_preview_export_and_download(client, tmp_path):
    response = client.post(
        "/api/preview",
        data={"settings": json.dumps({"width_mm": 100})},
        files={"image": ("sample.svg", sample_bytes(), "image/svg+xml")},
    )
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["manifest"]["settings"]["width_mm"] == 100
    assert len(preview["meshes"]) == 2
    assert not (tmp_path / "exports").exists()  # Changing controls is not a durable write.
    response = client.post(f"/api/export/{preview['id']}")
    assert response.status_code == 200
    download = client.get(response.json()["download_url"])
    assert download.status_code == 200
    with ZipFile(io.BytesIO(download.content)) as archive:
        assert "project.json" in archive.namelist()
        assert json.loads(archive.read("manifest.json"))["piece_count"] == 1
    assert client.post(f"/api/export/{preview['id']}").json() == response.json()


def test_invalid_geometry_and_json_are_actionable(client):
    for config in ("no-json", '{"width_mm":300}', '{"base_mm":0}'):
        response = client.post("/api/preview", data={"settings": config})
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], str)


def test_input_and_origin_restrictions(client):
    response = client.post("/api/preview", files={"image": ("bad.png", b"broken", "image/png")})
    assert response.status_code == 422
    assert client.post("/api/preview", content=b"x" * (13 * 1024 * 1024)).status_code == 413
    assert (
        client.post("/api/preview", headers={"Origin": "https://example.invalid"}).status_code
        == 403
    )


def test_only_exported_known_files_can_be_downloaded(client):
    identifier = str(uuid4())
    assert client.post(f"/api/export/{identifier}").status_code == 410
    assert client.get(f"/api/files/{identifier}/anything.env").status_code == 404
    assert client.get("/api/files/not-a-uuid/print-pack.zip").status_code == 422
    assert client.get(f"/api/files/{identifier}/print-pack.zip").status_code == 404


def test_explicit_public_origin_supports_proxy_preview_and_export(tmp_path):
    origin = "https://sample-api-ws1.local"
    client = TestClient(create_app(tmp_path / "exports", public_origin=origin))
    headers = {"Origin": origin}
    preview = client.post("/api/preview", headers=headers, data={"settings": "{}"})
    assert preview.status_code == 200, preview.text
    exported = client.post(f"/api/export/{preview.json()['id']}", headers=headers)
    assert exported.status_code == 200
    for other in ("https://other.local", "http://sample-api-ws1.local", origin + ":9999"):
        rejected = client.post(
            "/api/preview", headers={"Origin": other, "X-Forwarded-Host": "sample-api-ws1.local"}
        )
        assert rejected.status_code == 403


@pytest.mark.parametrize(
    "origin", ["*", "https://sample.local/path", "https://user@sample.local", "https://sample.local#x"]
)
def test_public_origin_must_be_explicit_origin(origin):
    with pytest.raises(ValueError, match="Public origin"):
        create_app(public_origin=origin)


def test_server_exposes_defaults_and_health(client):
    assert client.get("/api/health").json()["processing"] == "local"
    assert client.get("/api/defaults").json()["bed_width_mm"] == 230
    assert client.get("/api/sample").content == sample_bytes()
