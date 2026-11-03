"""Loopback-only HTTPS/Blob fixture for the native iOS simulator checks."""

import argparse
import ipaddress
import os
import struct
import sys
import tempfile
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import uvicorn
from azure.storage.blob import BlobServiceClient
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from fastapi import Response
from playwright.sync_api import sync_playwright

from app.config import Settings
from app.main import create_app
from app.services.linkedin.crawler import LinkedInCrawler
from app.worker import run_worker
from conftest import FakeAI
from test_crawler import options
from test_crawler_browser import card, site

FIRST = "RAG native integration: evaluate retrieval independently."
SECOND = "RAG native background update: measure source recall."
LOGIN = "test-login-passphrase-with-32-characters"


def image():
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!2I5B", 400, 225, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\0" + b"\xd7\x19\x20" * 400) * 225))
        + chunk(b"IEND", b"")
    )


def collect(application, number, image_url):
    text = FIRST if number == 1 else SECOND
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_context(proxy={"server": "http://127.0.0.1:1"}).new_page()
            site(page, card(number, text).replace("https://media.licdn.com/fixture.svg", image_url))
            crawler = LinkedInCrawler(options(max_posts=1, max_scrolls=1))
            result = crawler.collect_page(page)
        finally:
            browser.close()
    assert len(result.posts) == 1 and result.posts[0].original_text == text
    crawler.collect = lambda: result
    status = run_worker(application.state.reader, options(), crawler)
    assert status.status == "completed" and status.extracted == 1
    return {"status": status.status, "text": text}


def fixture_app(settings, image_url):
    application = create_app(settings, ai=FakeAI())
    application.state.image_requests = 0

    @application.get("/fixture-image.png")
    def source_image():
        application.state.image_requests += 1
        return Response(image(), media_type="image/png")

    @application.post("/__fixture/collect")
    def second_batch():
        return collect(application, 2, image_url)

    @application.post("/__fixture/verify")
    def verify():
        posts = application.state.reader.posts()
        first = next(post for post in posts if post.original_text == FIRST)
        assert first.saved and first.read, "Native save/read operations did not persist"
        assert len(posts) == 2 and any(post.original_text == SECOND for post in posts)
        assert application.state.image_requests > 0, "Native source image was not requested"
        assert application.state.store.keys("linkedin/raw/")
        assert len(application.state.store.keys("linkedin/processed/")) == 2
        return {"posts": len(posts), "saved": first.saved, "read": first.read, "storage": settings.storage}

    return application


def certificate(directory):
    directory.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SIGNAL isolated simulator fixture")])
    root = (
        x509.CertificateBuilder().subject_name(root_name).issuer_name(root_name)
        .public_key(root_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=False, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False,
        ), critical=True).sign(root_key, hashes.SHA256())
    )
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(root.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        ]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=True,
            data_encipherment=False, key_agreement=False, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False,
        ), critical=True).sign(root_key, hashes.SHA256())
    )
    (directory / "root.pem").write_bytes(root.public_bytes(serialization.Encoding.PEM))
    (directory / "server.pem").write_bytes(server.public_bytes(serialization.Encoding.PEM))
    private = directory / "server-key.pem"
    private.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
    ))
    private.chmod(0o600)


def serve(directory, port):
    connection = os.environ["SIGNAL_TEST_AZURITE_CONNECTION_STRING"]
    fields = dict(part.split("=", 1) for part in connection.split(";") if part)
    endpoint = urlsplit(fields.get("BlobEndpoint", ""))
    if endpoint.scheme != "http" or endpoint.hostname not in ("localhost", "127.0.0.1"):
        raise ValueError("Native fixtures may only use a loopback storage emulator")
    container_name = "signal-native-" + uuid4().hex
    with tempfile.TemporaryDirectory(prefix="signal-native-") as local_path:
        with BlobServiceClient.from_connection_string(connection) as service:
            service.create_container(container_name)
            try:
                settings = Settings(
                    _env_file=None, storage="azure", storage_account="signaltest",
                    storage_container=container_name, local_path=local_path, scheduler_enabled=False,
                    login_secret=LOGIN, session_secret="independent-test-secret-with-32-characters",
                )
                with patch("app.services.storage.DefaultAzureCredential", return_value=SimpleNamespace(close=lambda: None)):
                    with patch("app.services.storage.BlobServiceClient", side_effect=lambda *a, **k: BlobServiceClient.from_connection_string(connection)):
                        application = fixture_app(settings, f"https://localhost:{port}/fixture-image.png")
                collect(application, 1, f"https://localhost:{port}/fixture-image.png")
                uvicorn.run(
                    application, host="127.0.0.1", port=port, log_level="warning",
                    ssl_certfile=str(directory / "server.pem"), ssl_keyfile=str(directory / "server-key.pem"),
                )
            finally:
                service.delete_container(container_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("certificate", "serve"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--port", type=int, default=8443)
    arguments = parser.parse_args()
    if arguments.command == "certificate":
        certificate(arguments.directory)
    else:
        serve(arguments.directory, arguments.port)
