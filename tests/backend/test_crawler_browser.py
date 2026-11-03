from html import escape
from urllib.parse import urlsplit

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright

from app.services.linkedin.crawler import CrawlError, LinkedInCrawler
from app.worker import run_worker
from test_crawler import options


@pytest.fixture(scope="module")
def playwright():
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="module")
def browser(playwright):
    browser = playwright.chromium.launch()
    yield browser
    browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(proxy={"server": "http://127.0.0.1:1"})
    yield context.new_page()
    context.close()


def card(number, text, *, expand=False):
    more = '<button class="inline-show-more-text__button" onclick="this.previousElementSibling.innerText += \' Expanded technical details.\'; this.remove()">see more</button>' if expand else ""
    return f"""<div data-urn="urn:li:activity:{number}">
      <a class="update-components-actor__meta-link" href="/in/fixture-author/">
        <span class="update-components-actor__name">Fixture Author</span></a>
      <div class="update-components-text"><span class="break-words">{escape(text)}</span>{more}</div>
      <time datetime="2026-11-02T00:00:00Z"></time>
      <div class="update-components-image"><img src="https://media.licdn.com/fixture.svg"></div>
    </div>"""


def site(page, html, *, destination="/feed/", invalid_action=False, login_status=200):
    requests = []

    def handle(route):
        request = route.request
        requests.append(request.url)
        path = urlsplit(request.url).path
        if request.url.startswith("https://media.licdn.com/"):
            route.fulfill(content_type="image/svg+xml", body='<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"/>')
        elif request.url == "https://www.linkedin.com/login":
            if login_status != 200:
                route.fulfill(status=login_status, content_type="text/html", body="<h1>Access unavailable</h1>")
                return
            action = "https://attacker.invalid/steal" if invalid_action else "/uas/login-submit"
            route.fulfill(content_type="text/html", body=f"""
              <form method="post" action="{action}">
              <input id="username" name="username"><input id="password" name="password" type="password">
              <button type="submit">Sign in</button></form>""")
        elif path == "/uas/login-submit":
            assert "fixture-password-not-real" in request.post_data
            route.fulfill(content_type="text/html", body=f"<script>location.replace({destination!r})</script>")
        elif request.url == "https://www.linkedin.com" + destination:
            route.fulfill(content_type="text/html", body=html)
        else:
            route.abort()

    page.route("**/*", handle)
    return requests


def test_real_browser_login_expansion_images_and_api(page, application, client, auth):
    site(page, card(123, "RAG requires source-grounded evaluation.", expand=True))
    crawler = LinkedInCrawler(options(max_scrolls=1))
    result = crawler.collect_page(page)
    assert len(result.posts) == 1
    post = result.posts[0]
    assert post.original_text == "RAG requires source-grounded evaluation. Expanded technical details."
    assert str(post.url) == "https://www.linkedin.com/feed/update/urn:li:activity:123/"
    assert str(post.author_url) == "https://www.linkedin.com/in/fixture-author/"
    assert post.author == "Fixture Author"
    assert post.published_at.isoformat() == "2026-11-02T00:00:00+00:00"
    assert list(map(str, post.image_urls)) == ["https://media.licdn.com/fixture.svg"]
    crawler.collect = lambda: result
    status = run_worker(application.state.reader, options(), crawler)
    assert status.status == "completed"
    response = client.get("/api/posts", headers=auth)
    assert response.json()["items"][0]["original_text"] == post.original_text


def test_browser_challenge_does_not_bypass_or_collect(page):
    requests = site(page, "<h1>Verify your account</h1>", destination="/checkpoint/challenge/")
    with pytest.raises(CrawlError, match="account_challenge"):
        LinkedInCrawler(options()).collect_page(page)
    assert not any(url.endswith("/feed/") for url in requests)


def test_browser_blocks_external_password_destination(page):
    requests = site(page, "", invalid_action=True)
    with pytest.raises(CrawlError, match="unexpected_login_destination"):
        LinkedInCrawler(options()).collect_page(page)
    assert not any("attacker" in url for url in requests)


def test_browser_caps_posts_and_deduplicates_visible_cards(page):
    html = card(1, "RAG first") + card(2, "RAG first") + card(3, "RAG second") + card(4, "RAG third")
    site(page, html)
    result = LinkedInCrawler(options(max_posts=2)).collect_page(page)
    assert [post.original_text for post in result.posts] == ["RAG first", "RAG second"]
    assert result.limit_reached


def test_browser_unsupported_markup_fails_visibly(page):
    site(page, '<div data-urn="urn:li:activity:1"><p>Unknown card markup</p></div>')
    with pytest.raises(CrawlError, match="unsupported_feed_markup"):
        LinkedInCrawler(options(max_scrolls=1)).collect_page(page)


def test_browser_explicit_empty_feed_is_not_an_error(page):
    site(page, '<main data-test-id="feed-empty-state">No posts</main>')
    result = LinkedInCrawler(options(max_scrolls=1)).collect_page(page)
    assert result.posts == []
    assert not result.limit_reached


@pytest.mark.parametrize("status", [403, 429])
def test_browser_stops_before_login_when_access_restricted(page, status):
    requests = site(page, "", login_status=status)
    with pytest.raises(CrawlError, match="access_restricted"):
        LinkedInCrawler(options()).collect_page(page)
    assert not any("/uas/" in url for url in requests)
