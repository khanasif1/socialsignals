import json
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.services.reader import now


def ingest(client, auth, data):
    result = client.post("/api/linkedin/import", headers=auth,
                         files={"file": ("posts.json", json.dumps([data]), "application/json")})
    assert result.status_code == 200, result.text
    result = client.post("/api/linkedin/sync", headers=auth)
    assert result.status_code == 202, result.text
    return client.get("/api/posts", headers=auth).json()["items"][0]


@pytest.mark.parametrize("installed", [False, True])
def test_health_and_auth(client, monkeypatch, installed):
    monkeypatch.setattr("app.main.Path", lambda path: SimpleNamespace(is_file=lambda: installed))
    assert client.get("/api/health").json() == {"status": "ok", "storage": "connected", "worker_image": installed}
    for path in ("/api/posts", "/api/bookmarks", "/api/settings", "/api/linkedin/status", "/api/statistics"):
        assert client.get(path).status_code == 401
    assert client.post("/api/auth/login", json={"secret": "wrong"}).status_code == 401


def test_login_rate_limit(client):
    for _ in range(10):
        assert client.post("/api/auth/login", json={"secret": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"secret": "wrong"}).status_code == 429


def test_logout_revokes(client, auth):
    assert client.delete("/api/auth/session", headers=auth).status_code == 200
    assert client.get("/api/settings", headers=auth).status_code == 401


def test_import_sync_filter_and_details(client, auth, post_data):
    post = ingest(client, auth, post_data)
    assert post["original_text"] == post_data["original_text"]
    assert post["generation"] == "llm"
    assert client.get(f"/api/posts/{post['id']}", headers=auth).json()["author"] == "Authorized Author"
    for query in ("topic=RAG", "q=retrieval", "category=AI%20Architecture", "author=Authorized",
                  "min_relevance=90", "date_from=2026-11-01&date_to=2026-11-03"):
        result = client.get(f"/api/posts?{query}", headers=auth)
        assert result.status_code == 200
        assert result.json()["total"] == 1
    assert client.get("/api/posts?q=unrelated", headers=auth).json()["total"] == 0
    assert client.get("/api/posts?page=0", headers=auth).status_code == 422
    assert client.get("/api/posts?date_from=2026-11-03&date_to=2026-11-01", headers=auth).status_code == 422
    assert client.get("/api/posts/featured", headers=auth).json()[0]["id"] == post["id"]
    assert client.get("/api/posts/topics", headers=auth).json()[0]["count"] == 1
    assert client.get("/api/statistics", headers=auth).json()["total_posts"] == 1


def test_bookmarks_read_and_explain(client, auth, post_data):
    post = ingest(client, auth, post_data)
    id = post["id"]
    assert client.post(f"/api/bookmarks/{id}", headers=auth).status_code == 200
    assert client.get("/api/bookmarks", headers=auth).json()[0]["saved"]
    assert client.put(f"/api/posts/{id}/read", headers=auth, json={"read": True}).status_code == 200
    assert client.get("/api/posts?read=false", headers=auth).json()["total"] == 0
    assert client.get("/api/posts/recommended", headers=auth).json() == []
    assert client.post(f"/api/posts/{id}/explain", headers=auth).json()["architect"] == "Architecture"
    assert client.delete(f"/api/bookmarks/{id}", headers=auth).status_code == 200
    assert client.get("/api/bookmarks", headers=auth).json() == []


def test_duplicate_export_is_idempotent(client, auth, post_data):
    first = ingest(client, auth, post_data)
    second = ingest(client, auth, post_data)
    assert first["id"] == second["id"]
    assert client.get("/api/posts", headers=auth).json()["total"] == 1
    assert client.get("/api/statistics", headers=auth).json()["total_posts"] == 1


def test_explanation_provenance_is_server_controlled(application, client, auth, post_data, monkeypatch):
    post = ingest(client, auth, post_data)
    original = application.state.ai.explain
    monkeypatch.setattr(application.state.ai, "explain", lambda post: original(post).model_copy(update={"generated": False}))
    url = f"/api/posts/{post['id']}/explain"
    assert client.post(url, headers=auth).json()["generated"] is True
    key = f"configuration/explanations/{post['id']}.json"
    cached = application.state.store.read(key)
    assert cached["generated"] is True
    with application.state.store.writer():
        application.state.store.write(key, {**cached, "generated": False})
    assert client.post(url, headers=auth).json()["generated"] is True


def test_retention_preserves_saved_content(application, client, auth, post_data):
    post_data = {**post_data, "image_urls": ["https://media.licdn.com/dms/image/example.jpg"]}
    post = ingest(client, auth, post_data)
    client.post(f"/api/bookmarks/{post['id']}", headers=auth)
    store = application.state.store
    old_date = (now() - timedelta(days=4)).date().isoformat()
    with store.writer():
        for prefix in ("linkedin/raw/", "linkedin/processed/"):
            for key in store.keys(prefix):
                data = store.read(key)
                store.write(key.replace(now().date().isoformat(), old_date), data)
                store.delete(key)
    application.state.reader.cleanup()
    assert store.keys("linkedin/raw/") == []
    assert store.keys("linkedin/processed/") == []
    assert client.get("/api/bookmarks", headers=auth).json()[0]["id"] == post["id"]
    assert client.get("/api/bookmarks", headers=auth).json()[0]["image_urls"] == post_data["image_urls"]
    assert client.get(f"/api/posts/{post['id']}", headers=auth).status_code == 200
    assert store.read("metadata/ingestion-state.json")


def test_images_survive_processing_details_topics_and_bookmarks(application, client, auth, post_data):
    urls = ["https://media.licdn.com/dms/image/example.jpg", "https://media.licdn.com/dms/image/second.png"]
    data = {**post_data, "image_urls": urls}
    post = ingest(client, auth, data)
    assert post["image_urls"] == urls
    assert post["original_text"] == post_data["original_text"]
    assert client.get(f"/api/posts/{post['id']}", headers=auth).json()["image_urls"] == urls
    assert client.get("/api/posts/topics", headers=auth).json()[0]["featured"]["image_urls"] == urls
    assert client.get("/api/posts/featured", headers=auth).json()[0]["image_urls"] == urls
    assert client.post(f"/api/bookmarks/{post['id']}", headers=auth).status_code == 200
    assert client.get("/api/bookmarks", headers=auth).json()[0]["image_urls"] == urls
    raw_key = application.state.store.keys("linkedin/raw/")[0]
    assert application.state.store.read(raw_key)[0]["image_urls"] == urls


def test_reimport_adds_images_to_existing_and_saved_posts_without_regenerating(application, client, auth, post_data):
    post = ingest(client, auth, post_data)
    assert post["image_urls"] == []
    assert client.post(f"/api/bookmarks/{post['id']}", headers=auth).status_code == 200
    store = application.state.store
    original_raw = {key: store.read(key) for key in store.keys("linkedin/raw/")}
    urls = ["https://media.licdn.com/dms/image/added.jpg"]
    response = client.post("/api/linkedin/import", headers=auth,
                           files={"file": ("posts.json", json.dumps([{**post_data, "image_urls": urls}]))})
    assert response.status_code == 200
    assert client.get(f"/api/posts/{post['id']}", headers=auth).json()["image_urls"] == urls
    assert client.get("/api/bookmarks", headers=auth).json()[0]["image_urls"] == urls
    application.state.ai.fail = True
    assert client.post("/api/linkedin/sync", headers=auth).status_code == 202
    assert client.get("/api/linkedin/sync/status", headers=auth).json()["status"] == "completed"
    assert client.get("/api/posts", headers=auth).json()["total"] == 1
    for key, raw in original_raw.items():
        assert store.read(key) == raw
    processed = store.read(store.keys("linkedin/processed/")[0])[0]
    assert processed["image_urls"] == urls
    # Text-only reimports must not discard already supplied images.
    client.post("/api/linkedin/import", headers=auth, files={"file": ("posts.json", json.dumps([post_data]))})
    assert client.get(f"/api/posts/{post['id']}", headers=auth).json()["image_urls"] == urls


def test_pending_duplicate_keeps_images_in_either_order(client, auth, post_data):
    urls = ["https://media.licdn.com/dms/image/pending.jpg"]
    data = [post_data, {**post_data, "image_urls": urls}]
    response = client.post("/api/linkedin/import", headers=auth, files={"file": ("posts.json", json.dumps(data))})
    assert response.status_code == 200
    # A later text-only raw record can sort after the image-bearing import.
    client.post("/api/linkedin/import", headers=auth, files={"file": ("posts.json", json.dumps(data[::-1]))})
    client.post("/api/linkedin/sync", headers=auth)
    result = client.get("/api/posts", headers=auth).json()
    assert result["total"] == 1
    assert result["items"][0]["image_urls"] == urls


def test_invalid_image_import_fails_visibly(client, auth, post_data):
    response = client.post("/api/linkedin/import", headers=auth,
                           files={"file": ("posts.json", json.dumps([{**post_data, "image_urls": ["http://example.com/image.jpg"]}]))})
    assert response.status_code == 422
    assert "HTTPS image URLs" in response.json()["detail"]


def test_failure_retains_raw_and_retry(application, client, auth, post_data):
    application.state.ai.fail = True
    client.post("/api/linkedin/import", headers=auth, files={"file": ("posts.json", json.dumps([post_data]))})
    client.post("/api/linkedin/sync", headers=auth)
    assert client.get("/api/linkedin/sync/status", headers=auth).json()["status"] == "failed"
    assert application.state.store.keys("linkedin/raw/")
    application.state.ai.fail = False
    client.post("/api/linkedin/sync", headers=auth)
    assert client.get("/api/posts", headers=auth).json()["total"] == 1


def test_validation_and_restrictions(client, auth):
    assert client.get("/api/linkedin/status", headers=auth).json()["personal_feed_available"] is False
    assert client.get("/api/posts/unknown", headers=auth).status_code == 404
    assert client.put("/api/settings", headers=auth, json={"retention_days": 2}).status_code == 422
    result = client.post("/api/linkedin/import", headers=auth, files={"file": ("posts.json", '[{"original_text":"RAG","url":"https://evil.example/"}]')})
    assert result.status_code == 422
    assert client.post("/api/linkedin/import", headers=auth, files={"file": ("x.txt", "bad")}).status_code == 422


def test_oauth_state_and_denial(client, auth):
    from urllib.parse import parse_qs, urlparse
    response = client.post("/api/linkedin/connect", headers=auth)
    assert response.status_code == 200
    query = parse_qs(urlparse(response.json()["authorization_url"]).query)
    assert query["scope"] == ["openid profile"]
    assert client.get("/api/linkedin/callback?state=bad&code=x").status_code == 400
    state = query["state"][0]
    assert client.get(f"/api/linkedin/callback?state={state}&error=access_denied").status_code == 400
    assert client.get(f"/api/linkedin/callback?state={state}&code=x").status_code == 400


def test_preferences_roundtrip(client, auth):
    prefs = client.get("/api/settings", headers=auth).json()
    prefs.update(retention_days=14, preferred_topics=["MCP"], sync_frequency="hourly")
    assert client.put("/api/settings", headers=auth, json=prefs).json() == prefs
    assert client.get("/api/settings", headers=auth).json() == prefs


def test_sync_reservation_prevents_duplicates(client, auth):
    assert client.post("/api/linkedin/sync", headers=auth).status_code == 202
    # Simulate the short interval between reservation and the worker starting.
    store = client.app.state.store
    with store.writer():
        status = client.app.state.reader.status()
        status.status = "running"
        store.write("metadata/last-sync.json", status.model_dump(mode="json"))
    assert client.post("/api/linkedin/sync", headers=auth).status_code == 409
