import ssl
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from fastapi.testclient import TestClient

from app.config import Settings
from native_fixture import FIRST, LOGIN, SECOND, certificate, collect, fixture_app, image


def test_native_fixture_uses_actual_collection_and_authenticated_api(tmp_path):
    application = fixture_app(Settings(
        _env_file=None, local_path=str(tmp_path), scheduler_enabled=False,
        login_secret=LOGIN, session_secret="independent-test-secret-with-32-characters",
    ), "https://localhost:8443/fixture-image.png")
    with TestClient(application) as client:
        collect(application, 1, "https://localhost:8443/fixture-image.png")
        session = client.post("/api/auth/login", json={"secret": LOGIN})
        assert session.status_code == 200
        auth = {"Authorization": f"Bearer {session.json()['token']}"}
        assert client.get("/api/posts").status_code == 401
        post = client.get("/api/posts", headers=auth).json()["items"][0]
        assert post["original_text"] == FIRST
        assert post["image_urls"] == ["https://localhost:8443/fixture-image.png"]
        response = client.get("/fixture-image.png")
        assert response.headers["content-type"] == "image/png"
        assert response.content == image()
        assert client.post(f"/api/bookmarks/{post['id']}", headers=auth).status_code == 200
        assert client.put(f"/api/posts/{post['id']}/read", headers=auth, json={"read": True}).status_code == 200
        assert client.post("/__fixture/collect").json()["text"] == SECOND
        assert client.post("/__fixture/verify").json() == {
            "posts": 2, "saved": True, "read": True, "storage": "local",
        }


def test_native_fixture_generates_loadable_isolated_tls(tmp_path):
    certificate(tmp_path)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(tmp_path / "server.pem", tmp_path / "server-key.pem")
    trust = ssl.create_default_context(cafile=str(tmp_path / "root.pem"))
    assert trust.cert_store_stats()["x509_ca"] == 1
    assert not list(Path(tmp_path).glob("*root*key*"))
