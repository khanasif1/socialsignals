from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class RawPost(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    author: str | None = None
    author_url: HttpUrl | None = None
    url: HttpUrl | None = None
    published_at: datetime | None = None
    original_text: str = Field(min_length=1, max_length=100_000)
    image_urls: list[HttpUrl] = Field(default_factory=list, max_length=10)
    imported_at: datetime
    source: Literal["linkedin_export", "linkedin_crawler"] = "linkedin_export"

    @field_validator("url", "author_url")
    @classmethod
    def linkedin_url(cls, value):
        if value and not (value.host == "linkedin.com" or value.host.endswith(".linkedin.com")):
            raise ValueError("Only LinkedIn source URLs are supported")
        return value

    @field_validator("image_urls")
    @classmethod
    def source_images(cls, value: list[HttpUrl]) -> list[HttpUrl]:
        if any(url.scheme != "https" or url.username or url.password for url in value):
            raise ValueError("Source images must use HTTPS URLs without embedded credentials")
        return list(dict.fromkeys(value))


class Insight(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=80)
    topics: list[str] = Field(max_length=15)
    summary: str = Field(max_length=4000)
    main_insight: str = Field(max_length=4000)
    patterns: list[str] = Field(max_length=15)
    technologies: list[str] = Field(max_length=30)
    practical_relevance: str = Field(max_length=4000)
    why_it_matters: str = Field(max_length=4000)
    depth_score: int = Field(ge=0, le=100)
    relevance_score: int = Field(ge=0, le=100)
    tags: list[str] = Field(max_length=20)
    duplicate_of: str | None = None


class Post(RawPost):
    insight: Insight
    generation: Literal["llm", "demo"]
    read: bool = False
    saved: bool = False


class PostPage(BaseModel):
    items: list[Post]
    total: int
    page: int
    page_size: int


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retention_days: Literal[1, 3, 7, 14, 30] = 3
    max_posts_per_sync: int = Field(default=100, ge=1, le=500)
    min_relevance_score: int = Field(default=35, ge=0, le=100)
    summary_length: Literal["short", "medium", "long"] = "short"
    preferred_topics: list[str] = Field(default_factory=list, max_length=20)
    sync_frequency: Literal["manual", "hourly", "daily"] = "manual"
    theme: Literal["dark", "light"] = "light"
    font_size: Literal["standard", "large"] = "standard"


class SyncStatus(BaseModel):
    status: Literal["never", "running", "completed", "failed"] = "never"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    imported: int = 0
    relevant: int = 0
    duplicates: int = 0
    remaining: int = 0
    message: str = "Upload an official LinkedIn export to begin."


class CrawlStatus(BaseModel):
    enabled: bool = False
    status: Literal["never", "disabled", "running", "completed", "failed", "action_required"] = "never"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_success_at: datetime | None = None
    extracted: int = 0
    skipped: int = 0
    limit_reached: bool = False
    code: str = "not_configured"
    message: str = "Background collection is not configured."


class IntegrationStatus(BaseModel):
    mode: Literal["export", "crawler"] = "export"
    connected: bool
    oauth_available: bool
    personal_feed_available: Literal[False] = False
    message: str
    crawler: CrawlStatus = Field(default_factory=CrawlStatus)


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    storage: Literal["connected", "unavailable"]
    worker_image: bool = False


class Topic(BaseModel):
    name: str
    count: int
    latest: datetime | None
    featured: Post


class Statistics(BaseModel):
    total_posts: int
    relevant_posts: int
    unread_posts: int
    by_topic: dict[str, int]
    by_author: dict[str, int]
    latest_sync: SyncStatus


class Explanation(BaseModel):
    executive: str = Field(max_length=6000)
    architect: str = Field(max_length=6000)
    technical: str = Field(max_length=10000)
    generated: bool = True


class LoginRequest(BaseModel):
    secret: str = Field(min_length=1, max_length=1024)


class Session(BaseModel):
    token: str
    expires_at: datetime


class ReadRequest(BaseModel):
    read: bool


class ConnectResponse(BaseModel):
    authorization_url: str


class Message(BaseModel):
    message: str
