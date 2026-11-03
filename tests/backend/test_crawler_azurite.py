import os
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

pytest.importorskip("playwright")

from azure.storage.blob import BlobServiceClient
from app.config import Settings
from app.main import create_app
from conftest import FakeAI
from test_crawler_browser import browser, page, playwright
from test_crawler_e2e import test_crawler_to_real_api_to_iphone_reader

pytestmark = pytest.mark.skipif(
    not os.environ.get("SIGNAL_TEST_AZURITE_CONNECTION_STRING"),
    reason="Set an isolated local Azurite connection string for the Blob-to-reader test",
)


@pytest.fixture
def application(monkeypatch, tmp_path):
    connection = os.environ["SIGNAL_TEST_AZURITE_CONNECTION_STRING"]
    fields = dict(part.split("=", 1) for part in connection.split(";") if part)
    endpoint = urlsplit(fields.get("BlobEndpoint", ""))
    assert endpoint.scheme == "http" and endpoint.hostname in (
        "localhost", "127.0.0.1", "host.docker.internal",
    ), "This test must only access a local storage emulator"
    container_name = "signal-test-" + uuid4().hex
    with BlobServiceClient.from_connection_string(connection) as service:
        service.create_container(container_name)
        monkeypatch.setattr("app.services.storage.DefaultAzureCredential", lambda: SimpleNamespace(close=lambda: None))
        monkeypatch.setattr(
            "app.services.storage.BlobServiceClient",
            lambda *args, **kwargs: BlobServiceClient.from_connection_string(connection),
        )
        settings = Settings(
            _env_file=None, storage="azure", storage_account="signaltest",
            storage_container=container_name, local_path=str(tmp_path), scheduler_enabled=False,
            login_secret="test-login-passphrase-with-32-characters",
            session_secret="independent-test-secret-with-32-characters",
        )
        application = create_app(settings, ai=FakeAI())
        try:
            yield application
        finally:
            service.delete_container(container_name)
