import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import Page, TimeoutError as BrowserTimeout, sync_playwright
from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models import RawPost
from app.services.linkedin import fingerprint, timestamp

CARDS = ':is(div[data-urn^="urn:li:activity:"], div.feed-shared-update-v2[data-id^="urn:li:activity:"])'
FEED = "https://www.linkedin.com/feed/"
LOGIN = "https://www.linkedin.com/login"


class CrawlError(Exception):
    def __init__(self, code: str, action_required: bool = False):
        super().__init__(code)
        self.code = code
        self.action_required = action_required


class CrawlerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SIGNAL_LINKEDIN_CRAWLER_", env_file=".env",
        extra="ignore", hide_input_in_errors=True,
    )
    enabled: bool = False
    username: SecretStr = SecretStr("")
    password: SecretStr = SecretStr("")
    max_posts: int = Field(default=100, ge=1, le=500)
    max_scrolls: int = Field(default=20, ge=1, le=100)
    max_seconds: int = Field(default=180, ge=10, le=600)
    max_processing_batches: int = Field(default=20, ge=1, le=100)
    processing_max_seconds: int = Field(default=600, ge=10, le=3600)
    navigation_timeout_ms: int = Field(default=30_000, ge=1000, le=60_000)


@dataclass
class CrawlResult:
    posts: list[RawPost]
    skipped: int
    limit_reached: bool


def linkedin_url(value: str | None) -> str | None:
    if not value:
        return None
    absolute = urljoin(FEED, value)
    parsed = urlsplit(absolute)
    if (parsed.scheme == "https" and not parsed.username and not parsed.password
            and parsed.hostname and (parsed.hostname == "linkedin.com" or parsed.hostname.endswith(".linkedin.com"))):
        return absolute
    return None


class LinkedInCrawler:
    """Best-effort visible-feed collection, without private APIs or challenge bypass."""

    def __init__(self, settings: CrawlerSettings):
        self.settings = settings

    def collect(self) -> CrawlResult:
        if not self.settings.enabled:
            raise CrawlError("disabled")
        if os.environ.get("PWDEBUG") or os.environ.get("DEBUG"):
            raise CrawlError("unsafe_browser_debug_configuration", action_required=True)
        for secret in (self.settings.username, self.settings.password):
            if not secret.get_secret_value().strip() or secret.get_secret_value().startswith("@Microsoft.KeyVault("):
                raise CrawlError("credentials_not_configured", action_required=True)
        # A fresh ephemeral context never persists credentials, cookies, or browser traces.
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                page = context.new_page()
                page.set_default_timeout(self.settings.navigation_timeout_ms)
                return self.collect_page(page)
            finally:
                browser.close()

    def _check_access(self, page: Page):
        if not linkedin_url(page.url):
            raise CrawlError("unexpected_login_destination", action_required=True)
        path = urlsplit(page.url).path.lower()
        if any(part in path for part in ("/checkpoint", "/challenge", "/authwall")):
            raise CrawlError("account_challenge", action_required=True)
        if page.locator('iframe[src*="captcha"], input[name="pin"], #input__phone_verification_pin').count():
            raise CrawlError("account_challenge", action_required=True)

    def collect_page(self, page: Page) -> CrawlResult:
        """Uses the same extraction path in production and isolated browser fixtures."""
        deadline = time.monotonic() + self.settings.max_seconds
        page.set_default_timeout(min(self.settings.navigation_timeout_ms, self.settings.max_seconds * 1000))
        response = page.goto(LOGIN, wait_until="domcontentloaded")
        if response and response.status in (401, 403, 429):
            raise CrawlError("access_restricted", action_required=True)
        if response and response.status >= 500:
            raise CrawlError("source_unavailable")
        self._check_access(page)
        username = page.locator("#username")
        password = page.locator("#password")
        username.wait_for(state="visible")
        form = password.locator("xpath=ancestor::form")
        submit = form.locator('button[type="submit"]').first
        form_action = submit.get_attribute("formaction") or form.get_attribute("action")
        if form_action and not linkedin_url(urljoin(page.url, form_action)):
            raise CrawlError("unexpected_login_destination", action_required=True)
        username.fill(self.settings.username.get_secret_value())
        password.fill(self.settings.password.get_secret_value())
        submit.click()
        login_deadline = min(deadline, time.monotonic() + self.settings.navigation_timeout_ms / 1000)
        while time.monotonic() < login_deadline:
            self._check_access(page)
            if urlsplit(page.url).path.startswith("/feed"):
                break
            if page.locator('#error-for-password:not(:empty), #error-for-username:not(:empty), [role="alert"]').count():
                raise CrawlError("login_rejected", action_required=True)
            page.wait_for_timeout(250)
        else:
            raise CrawlError("login_not_completed", action_required=True)
        self._check_access(page)
        try:
            page.locator(f'{CARDS}, [data-test-id="feed-empty-state"]').first.wait_for(state="attached")
        except BrowserTimeout as error:
            self._check_access(page)
            if not urlsplit(page.url).path.startswith("/feed"):
                raise CrawlError("session_expired", action_required=True) from error
            raise CrawlError("unsupported_feed_markup") from error
        posts: dict[str, RawPost] = {}
        skipped_ids: set[str] = set()
        stagnant = 0
        limited = False
        for scroll in range(self.settings.max_scrolls):
            self._check_access(page)
            if not urlsplit(page.url).path.startswith("/feed"):
                raise CrawlError("session_expired", action_required=True)
            if time.monotonic() >= deadline:
                limited = True
                break
            for button in page.locator(
                f'{CARDS} button.feed-shared-inline-show-more-text__see-more-less-toggle, '
                f'{CARDS} button.inline-show-more-text__button'
            ).filter(has_text=re.compile(r"see more|[.]{3}more|\u2026more", re.I)).all()[:self.settings.max_posts]:
                if time.monotonic() >= deadline:
                    limited = True
                    break
                button.click(timeout=min(3000, self.settings.navigation_timeout_ms))
            records = page.locator(CARDS).evaluate_all("""cards => cards.slice(0, 500).map(card => {
                const body = card.querySelector('.update-components-text .break-words, .update-components-text, .feed-shared-update-v2__description');
                const author = card.querySelector('.update-components-actor__name [aria-hidden="true"], .update-components-actor__name');
                return {
                    urn: card.getAttribute('data-urn') || card.getAttribute('data-id'),
                    text: body?.innerText,
                    author: author?.innerText,
                    author_url: card.querySelector('a.update-components-actor__meta-link')?.getAttribute('href'),
                    published_at: card.querySelector('time[datetime]')?.getAttribute('datetime'),
                    images: Array.from(card.querySelectorAll('.update-components-image img, .feed-shared-image img'))
                        .map(image => image.currentSrc || image.src).slice(0, 10)
                };
            })""")
            previous = len(posts)
            for record in records:
                text = record.get("text")
                activity = re.fullmatch(r"urn:li:activity:(\d+)", record.get("urn") or "")
                if not text or not text.strip() or len(text) > 100_000 or not activity:
                    skipped_ids.add(record.get("urn") or "unknown")
                    continue
                images = []
                for image in record["images"]:
                    parsed = urlsplit(image)
                    if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
                        images.append(image)
                try:
                    raw = RawPost(
                        id=fingerprint(text), original_text=text,
                        author=(record.get("author") or "").strip() or None,
                        author_url=linkedin_url(record.get("author_url")),
                        url=f"{FEED}update/{activity.group()}/",
                        published_at=timestamp(record.get("published_at")), image_urls=images,
                        imported_at=datetime.now(timezone.utc), source="linkedin_crawler",
                    )
                except ValidationError:
                    skipped_ids.add(record["urn"])
                    continue
                posts[raw.id] = raw
                if len(posts) >= self.settings.max_posts:
                    limited = True
                    break
            if len(posts) >= self.settings.max_posts:
                break
            stagnant = stagnant + 1 if len(posts) == previous else 0
            if stagnant >= 3 or page.locator('[data-test-id="feed-empty-state"]').count():
                break
            page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            page.wait_for_timeout(min(1000, max(0, int((deadline - time.monotonic()) * 1000))))
            limited = scroll == self.settings.max_scrolls - 1
        if skipped_ids and not posts:
            raise CrawlError("unsupported_feed_markup")
        return CrawlResult(list(posts.values()), len(skipped_ids), limited)
