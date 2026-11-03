import os
import re
import socket
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

pytest.importorskip("playwright")
import uvicorn
from playwright.sync_api import expect

from app.services.linkedin import fingerprint
from app.services.linkedin.crawler import CrawlResult, LinkedInCrawler
from app.worker import run_worker
from test_crawler import options
from test_crawler_browser import browser, card, page, playwright, site


@pytest.mark.skipif(not os.environ.get("SIGNAL_TEST_READER_URL"), reason="Set SIGNAL_TEST_READER_URL to the local Expo preview")
def test_crawler_to_real_api_to_iphone_reader(page, playwright, application, client):
    preview = os.environ["SIGNAL_TEST_READER_URL"].rstrip("/")
    assert urlsplit(preview).hostname in ("localhost", "127.0.0.1", "host.docker.internal")
    site(page, card(123, "RAG end-to-end fixture: evaluate retrieval independently."))
    collector = LinkedInCrawler(options(max_posts=1))
    result = collector.collect_page(page)
    collector.collect = lambda: result
    assert run_worker(application.state.reader, options(), collector).status == "completed"
    application.state.settings.cors_origins.append(preview)

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(application, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    mobile = None
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        assert server.started, "Local fixture API failed to start"
        mobile = playwright.webkit.launch()
        context = mobile.new_context(
            **{**playwright.devices["iPhone 13 Pro Max"], "viewport": {"width": 428, "height": 926}},
        )
        phone = context.new_page()
        phone.set_default_timeout(30_000)
        phone.clock.install()
        phone.add_init_script("localStorage.setItem('signal-mode', 'live')")

        def api_proxy(route):
            requested = urlsplit(route.request.url)
            target = f"http://127.0.0.1:{port}{requested.path}"
            if requested.query:
                target += "?" + requested.query
            response = route.fetch(url=target)
            route.fulfill(response=response)

        phone.route("**/api/**", api_proxy)
        phone.route("https://media.licdn.com/**", lambda route: route.fulfill(
            content_type="image/svg+xml",
            body='<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450"><rect width="100%" height="100%" fill="#D71920"/></svg>',
        ))
        phone.goto(preview + "/settings")
        expect(phone.get_by_text("Sign in using the private passphrase configured on your backend.", exact=True)).to_be_visible()
        phone.get_by_label("Private backend passphrase", exact=True).fill("test-login-passphrase-with-32-characters")
        phone.get_by_role("button", name="Connect private backend", exact=True).click()
        expect(phone.get_by_text("Signed in. Your session is stored securely on iOS.", exact=True)).to_be_visible()
        phone.get_by_role("tab", name=re.compile("Today")).click()
        phone.get_by_role("button", name=f"Read {result.posts[0].original_text}", exact=True).first.click()
        expect(phone.get_by_text("THE ORIGINAL POST", exact=True)).to_be_visible()
        expect(phone.get_by_text(result.posts[0].original_text, exact=True).last).to_be_visible()
        phone.get_by_role("button", name="Back to your reading", exact=True).click()
        text = "RAG second background fixture: measure source recall before changing models."
        second = result.posts[0].model_copy(update={"id": fingerprint(text), "original_text": text})
        source = SimpleNamespace(collect=lambda: CrawlResult([second], 0, False))
        assert run_worker(application.state.reader, options(), source).status == "completed"
        phone.clock.fast_forward(60_000)
        read_second = phone.get_by_role("button", name=f"Read {text}", exact=True).first
        expect(read_second).to_be_visible(timeout=15_000)
        read_second.click()
        expect(phone.get_by_text(text, exact=True).last).to_be_visible()
        phone.evaluate("() => document.fonts.ready")
        assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth")
        store = application.state.store
        assert store.keys("linkedin/raw/")
        assert len(store.keys("linkedin/processed/")) == 2
        assert store.read("metadata/last-crawl.json")["status"] == "completed"
        name = "crawler-blob-to-reader-iphone.png" if application.state.settings.storage == "azure" else "crawler-to-reader-iphone.png"
        output = Path(__file__).resolve().parents[2] / "frontend" / "test-results" / name
        output.parent.mkdir(parents=True, exist_ok=True)
        phone.screenshot(path=str(output))
    finally:
        if mobile:
            mobile.close()
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        assert not thread.is_alive(), "Fixture API did not stop"
