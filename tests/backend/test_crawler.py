import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

pytest.importorskip("playwright")

from app.models import RawPost
from app.services.linkedin import fingerprint
from app.services.linkedin.crawler import CrawlError, CrawlerSettings, CrawlResult, LinkedInCrawler, linkedin_url
from app.services.storage import BusyError, JsonStore
from app.worker import STATUS_KEY, run_worker


def options(**kwargs):
    return CrawlerSettings(
        _env_file=None, enabled=True, username="fixture-user-not-real",
        password="fixture-password-not-real", **kwargs,
    )


def raw(text="RAG retrieval and generation need independent evaluation."):
    return RawPost(
        id=fingerprint(text), original_text=text, source="linkedin_crawler",
        imported_at=datetime.now(timezone.utc), image_urls=["https://media.licdn.com/fixture.jpg"],
    )


def fake_source(posts=None):
    return SimpleNamespace(collect=lambda: CrawlResult(posts or [raw()], 0, False))


def test_worker_imports_processes_and_api_reads(application, client, auth):
    reader = application.state.reader
    assert reader.preferences().sync_frequency == "manual"
    result = run_worker(reader, options(), fake_source())
    assert result.status == "completed"
    assert result.extracted == 1
    post = client.get("/api/posts", headers=auth).json()["items"][0]
    assert post["original_text"] == raw().original_text
    assert post["source"] == "linkedin_crawler"
    assert post["image_urls"] == ["https://media.licdn.com/fixture.jpg"]
    assert reader.store.read("metadata/ingestion-state.json")["seen"][post["id"]]["done"]
    assert reader.store.keys("linkedin/raw/")
    assert reader.store.keys("linkedin/processed/")
    status = client.get("/api/linkedin/status", headers=auth).json()
    assert status["mode"] == "crawler"
    assert status["crawler"]["last_success_at"]
    assert status["personal_feed_available"] is False
    assert "fixture-password" not in json.dumps(status)
    run_worker(reader, options(), fake_source())
    assert client.get("/api/posts", headers=auth).json()["total"] == 1
    assert reader.status().imported == 0


def test_processing_resumes_in_multiple_batches(application):
    reader = application.state.reader
    with reader.store.writer():
        reader.store.write("configuration/preferences.json", {"max_posts_per_sync": 1})
    posts = [raw(f"RAG evaluation technical example number {i}.") for i in range(3)]
    result = run_worker(reader, options(), fake_source(posts))
    assert result.status == "completed"
    assert len(reader.posts()) == 3
    assert reader.status().remaining == 0


def test_processing_budget_keeps_pending_work_visible(application):
    reader = application.state.reader
    with reader.store.writer():
        reader.store.write("configuration/preferences.json", {"max_posts_per_sync": 1})
    posts = [raw(f"RAG evaluation technical example number {i}.") for i in range(3)]
    result = run_worker(reader, options(max_processing_batches=1), fake_source(posts))
    assert result.status == "completed"
    assert reader.status().remaining == 2
    assert "2 posts pending" in result.message


def test_processing_deadline_preserves_unprocessed_records(application):
    reader = application.state.reader
    reader.import_posts([raw()])
    reader.reserve_sync()
    reader.sync(deadline=0)
    assert reader.status().remaining == 1
    assert reader.status().imported == 0
    assert not reader.store.read("metadata/ingestion-state.json")["seen"][raw().id]["done"]
    assert run_worker(reader, options(), fake_source()).status == "completed"
    assert len(reader.posts()) == 1


def test_disabled_and_missing_configuration_do_not_login(application):
    reader = application.state.reader
    source = SimpleNamespace(collect=lambda: pytest.fail("Must not attempt login"))
    assert run_worker(reader, CrawlerSettings(_env_file=None), source).status == "disabled"
    reader.ai.client = False
    status = run_worker(reader, options(), source)
    assert status.status == "action_required"
    assert status.code == "ai_not_configured"
    with pytest.raises(CrawlError, match="credentials_not_configured"):
        LinkedInCrawler(CrawlerSettings(_env_file=None, enabled=True)).collect()


def test_challenge_pauses_until_explicit_resume(application):
    reader = application.state.reader

    def challenge():
        raise CrawlError("account_challenge", action_required=True)

    result = run_worker(reader, options(), SimpleNamespace(collect=challenge))
    assert result.status == "action_required"
    result = run_worker(reader, options(), SimpleNamespace(collect=lambda: pytest.fail("No automated challenge retries")))
    assert result.status == "action_required"
    assert run_worker(reader, options(), fake_source(), resume=True).status == "completed"


def test_browser_exception_text_never_enters_logs_or_status(application, caplog):
    def fail():
        raise RuntimeError("fixture-password-not-real <private HTML>")

    result = run_worker(application.state.reader, options(), SimpleNamespace(collect=fail))
    assert result.status == "failed"
    assert "fixture-password" not in caplog.text
    assert "private HTML" not in caplog.text
    assert "fixture-password" not in json.dumps(application.state.store.read(STATUS_KEY))


def test_unsafe_browser_debug_is_rejected(monkeypatch):
    monkeypatch.setenv("DEBUG", "pw:api")
    with pytest.raises(CrawlError, match="unsafe_browser_debug_configuration"):
        LinkedInCrawler(options()).collect()


def test_ai_failure_retains_raw_for_retry(application):
    reader = application.state.reader
    reader.ai.fail = True
    assert run_worker(reader, options(), fake_source()).code == "processing_failed"
    assert reader.store.keys("linkedin/raw/")
    assert not reader.store.read("metadata/ingestion-state.json")["seen"][raw().id]["done"]
    reader.ai.fail = False
    assert run_worker(reader, options(), fake_source()).status == "completed"
    assert len(reader.posts()) == 1


def test_crawl_lease_does_not_block_normal_writers(application):
    store = application.state.store

    def write():
        with store.writer():
            store.write("configuration/test.json", {"responsive": True})

    with store.lease("crawler"):
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(write).result(timeout=3)
    assert store.read("configuration/test.json")["responsive"]


def test_crawl_lease_blocks_second_worker(application):
    store = application.state.store
    other = JsonStore(application.state.settings)
    try:
        with store.lease("crawler"):
            with pytest.raises(BusyError):
                with other.lease("crawler"):
                    pytest.fail("Concurrent crawl acquired the lease")
    finally:
        other.close()


@pytest.mark.parametrize("name", ["writer", "crawler"])
def test_blob_transport_failure_marks_lease_lost(application, monkeypatch, caplog, name):
    from unittest.mock import MagicMock
    from azure.core.exceptions import ServiceRequestError

    class Event:
        def __init__(self):
            self.value = False

        def set(self):
            self.value = True

        def is_set(self):
            return self.value

        def wait(self, timeout):
            return self.value

    lease = MagicMock()
    lease.renew.side_effect = ServiceRequestError("private transport diagnostics")
    store = application.state.store
    store.container = MagicMock()
    monkeypatch.setattr("app.services.storage.BlobLeaseClient", lambda blob: lease)
    monkeypatch.setattr("app.services.storage.threading", SimpleNamespace(
        Event=Event,
        Thread=lambda target, daemon: SimpleNamespace(start=target, join=lambda timeout: None),
    ))
    with pytest.raises(BusyError, match="Storage lease lost"):
        with store.lease(name) as failed:
            assert failed.is_set()
    assert f"{name} lease renewal failed (ServiceRequestError)" in caplog.text
    assert "private transport diagnostics" not in caplog.text
    lease.release.assert_called_once()


@pytest.mark.parametrize("value", [
    "https://linkedin.com.attacker.invalid/feed/", "http://www.linkedin.com/feed/",
    "https://user:password@www.linkedin.com/login", "//attacker.invalid/login",
])
def test_login_destination_guards(value):
    assert linkedin_url(value) is None


def test_worker_uses_blob_json_across_reader_instances(monkeypatch, tmp_path):
    from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
    from fastapi.testclient import TestClient
    from unittest.mock import MagicMock

    from app.config import Settings
    from app.main import create_app
    from app.services.reader import Reader
    from conftest import FakeAI

    documents = {}
    lock_names = []

    class Container:
        def upload_blob(self, name, data, overwrite=False, **kwargs):
            if name in documents and not overwrite:
                raise ResourceExistsError("Fixture blob exists")
            documents[name] = data

        def download_blob(self, name):
            if name not in documents:
                raise ResourceNotFoundError("Fixture blob missing")
            return SimpleNamespace(readall=lambda: documents[name])

        def list_blobs(self, name_starts_with):
            return [SimpleNamespace(name=name) for name in documents if name.startswith(name_starts_with)]

        def get_blob_client(self, name):
            lock_names.append(name)
            return SimpleNamespace(upload_blob=lambda data, **kwargs: self.upload_blob(name, data, **kwargs))

        def get_container_properties(self):
            return {}

        def delete_blob(self, name):
            documents.pop(name)

    service = MagicMock()
    service.get_container_client.return_value = Container()
    monkeypatch.setattr("app.services.storage.DefaultAzureCredential", MagicMock)
    monkeypatch.setattr("app.services.storage.BlobServiceClient", lambda *args, **kwargs: service)
    monkeypatch.setattr("app.services.storage.BlobLeaseClient", lambda blob: MagicMock())
    settings = Settings(
        _env_file=None, storage="azure", storage_account="fixtureaccount",
        local_path=str(tmp_path), scheduler_enabled=False,
        login_secret="test-login-passphrase-with-32-characters",
        session_secret="independent-test-secret-with-32-characters",
    )
    store = JsonStore(settings)
    try:
        assert run_worker(Reader(store, FakeAI()), options(), fake_source()).status == "completed"
        api_store = JsonStore(settings)
        with TestClient(create_app(settings, store=api_store, ai=FakeAI())) as client:
            login = client.post("/api/auth/login", json={"secret": "test-login-passphrase-with-32-characters"}).json()
            response = client.get("/api/posts", headers={"Authorization": f"Bearer {login['token']}"})
            assert response.json()["items"][0]["source"] == "linkedin_crawler"
            assert response.json()["items"][0]["original_text"] == raw().original_text
        assert "metadata/crawler-lock.json" in lock_names
        assert "metadata/writer-lock.json" in lock_names
        assert any(name.startswith("linkedin/raw/") for name in documents)
        assert any(name.startswith("linkedin/processed/") for name in documents)
        assert "fixture-password-not-real" not in str(documents)
    finally:
        store.close()
