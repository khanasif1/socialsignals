import json
from datetime import timedelta
from unittest.mock import MagicMock

import httpx
import pytest
from cryptography.fernet import Fernet
from openai import OpenAI

from app.api.auth import encryption_key
from app.config import Settings
from app.models import Insight, Preferences
from app.services.ai import Intelligence
from app.services.linkedin import LinkedInExport
from app.services.reader import now
from app.services.storage import JsonStore


def test_unresolved_secret_references_fail_closed():
    with pytest.raises(ValueError) as error:
        Settings(
            _env_file=None, login_secret="@Microsoft.KeyVault(SecretUri=https://example.vault.azure.net/secrets/login/)",
            session_secret="independent-test-secret-with-32-characters",
        )
    assert "Key Vault references resolved" in str(error.value)
    assert "SecretUri" not in str(error.value)


def test_oauth_success_encrypts_token(application, client, auth, monkeypatch):
    from urllib.parse import parse_qs, urlparse
    response = client.post("/api/linkedin/connect", headers=auth)
    state = parse_qs(urlparse(response.json()["authorization_url"]).query)["state"][0]
    original_client = httpx.Client

    def handle(request):
        if request.url.path.endswith("accessToken"):
            return httpx.Response(200, json={"access_token": "private-linkedin-token", "expires_in": 3600})
        return httpx.Response(200, json={"sub": "authorized-member"})

    monkeypatch.setattr("app.main.httpx.Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    result = client.get(f"/api/linkedin/callback?state={state}&code=authorization-code")
    assert result.status_code == 200
    assert "private-linkedin-token" not in result.text
    record = application.state.store.read("configuration/linkedin.json")
    assert record["token_encrypted"] != "private-linkedin-token"
    key = encryption_key(application.state.settings.session_secret.get_secret_value())
    assert Fernet(key).decrypt(record["token_encrypted"].encode()) == b"private-linkedin-token"
    assert client.get("/api/linkedin/status", headers=auth).json()["connected"]


def test_ai_structured_output_adapter(post_data):
    settings = Settings(
        _env_file=None, login_secret="test-login-passphrase-with-32-characters",
        session_secret="independent-test-secret-with-32-characters",
        ai_provider="openai", openai_api_key="not-a-real-key",
    )
    ai = Intelligence(settings)
    ai.client.close()
    insight = Insight(
        title="RAG evaluation", category="AI Engineering", topics=["RAG"], summary="Evaluate sources.",
        main_insight="Separate retrieval and generation.", patterns=["Evaluation"], technologies=["RAG"],
        practical_relevance="Measure recall.", why_it_matters="Find failures.",
        depth_score=90, relevance_score=95, tags=["evaluation"],
    )

    def handle(request):
        payload = json.loads(request.content)
        assert payload["response_format"]["type"] == "json_schema"
        assert "untrusted data" in payload["messages"][0]["content"]
        assert "https://media.licdn.com/" not in request.content.decode()
        return httpx.Response(200, json={
            "id": "test", "object": "chat.completion", "created": 1, "model": "gpt-4o-mini",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": insight.model_dump_json()}}],
        })

    ai.client = OpenAI(api_key="not-a-real-key", http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    raw = LinkedInExport().parse(json.dumps([{**post_data, "image_urls": ["https://media.licdn.com/dms/image/private.jpg"]}]).encode(), "posts.json")[0]
    assert ai.analyze(raw, Preferences()) == insight
    ai.close()


def test_managed_identity_blob_writes_are_leased(monkeypatch, tmp_path):
    service = MagicMock()
    container = service.get_container_client.return_value
    blob = container.get_blob_client.return_value
    lease = MagicMock()
    credential = MagicMock()
    monkeypatch.setattr("app.services.storage.DefaultAzureCredential", lambda: credential)
    factory = MagicMock(return_value=service)
    monkeypatch.setattr("app.services.storage.BlobServiceClient", factory)
    monkeypatch.setattr("app.services.storage.BlobLeaseClient", lambda value: lease)
    settings = Settings(
        _env_file=None, login_secret="test-login-passphrase-with-32-characters",
        session_secret="independent-test-secret-with-32-characters",
        storage="azure", storage_account="privateaccount", local_path=str(tmp_path),
    )
    store = JsonStore(settings)
    with store.writer():
        store.write("configuration/preferences.json", {"theme": "dark"})
    assert factory.call_args.args[0] == "https://privateaccount.blob.core.windows.net"
    assert factory.call_args.kwargs["credential"] is credential
    lease.acquire.assert_called_once_with(lease_duration=60)
    lease.release.assert_called_once()
    container.upload_blob.assert_called_once()
    store.close()


def test_azure_ai_uses_entra_without_api_keys(monkeypatch):
    credential = MagicMock()
    credential_factory = MagicMock(return_value=credential)
    provider = MagicMock(return_value="test-entra-token")
    provider_factory = MagicMock(return_value=provider)
    client_factory = MagicMock()
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", credential_factory)
    monkeypatch.setattr("azure.identity.get_bearer_token_provider", provider_factory)
    monkeypatch.setattr("app.services.ai.AzureOpenAI", client_factory)
    settings = Settings(
        _env_file=None, login_secret="test-login-passphrase-with-32-characters",
        session_secret="independent-test-secret-with-32-characters",
        ai_provider="azure", azure_openai_endpoint="https://fixture.openai.azure.com/",
        azure_openai_deployment="gpt-4.1-mini",
    )
    ai = Intelligence(settings)
    provider_factory.assert_called_once_with(credential, "https://cognitiveservices.azure.com/.default")
    assert client_factory.call_args.kwargs["azure_ad_token_provider"] is provider
    assert "api_key" not in client_factory.call_args.kwargs
    assert ai.model == "gpt-4.1-mini"
    ai.close()
    credential.close.assert_called_once()


def test_batch_resume_and_semantic_deduplication(application, client, auth, post_data):
    prefs = client.get("/api/settings", headers=auth).json()
    prefs["max_posts_per_sync"] = 1
    client.put("/api/settings", headers=auth, json=prefs)
    data = [post_data, {**post_data, "original_text": "A paraphrase of the same evaluation guidance for RAG."}]
    client.post("/api/linkedin/import", headers=auth, files={"file": ("posts.json", json.dumps(data))})
    client.post("/api/linkedin/sync", headers=auth)
    assert client.get("/api/linkedin/sync/status", headers=auth).json()["remaining"] == 1
    previous = application.state.ai.analyze

    def duplicate(raw, preferences, candidates):
        insight = previous(raw, preferences, candidates)
        insight.duplicate_of = candidates[0]["id"]
        return insight

    application.state.ai.analyze = duplicate
    client.post("/api/linkedin/sync", headers=auth)
    assert client.get("/api/posts", headers=auth).json()["total"] == 1
    assert client.get("/api/linkedin/sync/status", headers=auth).json()["duplicates"] == 1


def test_abandoned_sync_reservation_recovers(application, client, auth):
    with application.state.store.writer():
        status = application.state.reader.status()
        status.status = "running"
        status.started_at = now() - timedelta(minutes=3)
        application.state.store.write("metadata/last-sync.json", status.model_dump(mode="json"))
    assert client.post("/api/linkedin/sync", headers=auth).status_code == 202


def test_import_auth_size_and_original_integrity(client, auth, post_data):
    assert client.post("/api/linkedin/import", files={"file": ("posts.json", "[]")}).status_code == 401
    result = client.post("/api/linkedin/import", headers={**auth, "content-length": str(12 * 1024 * 1024)},
                         content=b"")
    assert result.status_code == 413
    text = " \n Original post text with whitespace. \n "
    raw = LinkedInExport().parse(json.dumps([{**post_data, "original_text": text}]).encode(), "posts.json")[0]
    assert raw.original_text == text


def test_chunked_mobile_uploads_are_supported_and_bounded(client, auth, post_data):
    start = b'--signal-boundary\r\nContent-Disposition: form-data; name="file"; filename="posts.json"\r\nContent-Type: application/json\r\n\r\n'
    end = b"\r\n--signal-boundary--\r\n"
    headers = {**auth, "Content-Type": "multipart/form-data; boundary=signal-boundary"}
    response = client.post("/api/linkedin/import", headers=headers,
                           content=iter([start, json.dumps([post_data]).encode(), end]))
    assert response.status_code == 200
    response = client.post("/api/linkedin/import", headers=headers,
                           content=iter([start, *([b"x" * (1024 * 1024)] * 12), end]))
    assert response.status_code == 413
