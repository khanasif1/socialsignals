import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Literal
from urllib.parse import urlencode

import httpx
from azure.core.exceptions import AzureError
from cryptography.fernet import Fernet
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from openai import OpenAIError
from pydantic import ValidationError

from app.api.auth import digest, encryption_key, issue, require_session
from app.config import Settings, get_settings
from app.models import (
    ConnectResponse, Explanation, Health, IntegrationStatus, LoginRequest, Message, Post,
    PostPage, Preferences, ReadRequest, Session, Statistics, SyncStatus, Topic,
)
from app.services.ai import AIUnavailable, Intelligence
from app.services.linkedin import LinkedInExport, MAX_BYTES
from app.services.reader import Reader, now
from app.services.storage import BusyError, JsonStore
from app.utils import UploadLimit

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("signal")
# HTTP clients must not log token endpoint payloads or content.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("azure").setLevel(logging.WARNING)


def create_app(settings: Settings | None = None, store: JsonStore | None = None, ai=None):
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app):
        async def maintenance():
            while True:
                await asyncio.to_thread(app.state.reader.scheduled_tick)
                await asyncio.sleep(60)

        task = asyncio.create_task(maintenance()) if settings.scheduler_enabled else None
        yield
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        app.state.ai.close()
        app.state.store.close()

    app = FastAPI(title="SIGNAL", version="1.0.0", lifespan=lifespan,
                  docs_url="/docs" if settings.env == "development" else None,
                  redoc_url=None, openapi_url="/openapi.json" if settings.env == "development" else None)
    app.state.settings = settings
    app.state.store = store or JsonStore(settings)
    app.state.ai = ai or Intelligence(settings)
    app.state.reader = Reader(app.state.store, app.state.ai)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_credentials=False, allow_methods=["GET", "POST", "PUT", "DELETE"],
                       allow_headers=["Authorization", "Content-Type"])
    app.add_middleware(UploadLimit)

    @app.middleware("http")
    async def headers(request, call_next):
        if request.method == "POST" and request.url.path == "/api/linkedin/import":
            authorization = request.headers.get("authorization", "")
            if not authorization.startswith("Bearer "):
                return JSONResponse(status_code=401, content={"detail": "Sign in before uploading"})
            sessions = await asyncio.to_thread(app.state.store.read, "configuration/sessions.json", {})
            if sessions.get(digest(authorization[7:]), 0) <= now().timestamp():
                return JSONResponse(status_code=401, content={"detail": "Session expired"})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if settings.env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.exception_handler(BusyError)
    async def busy(request, error):
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(AzureError)
    async def azure_error(request, error):
        log.error("Storage operation failed (%s)", type(error).__name__)
        return JSONResponse(status_code=503, content={"detail": "Storage temporarily unavailable. Retry shortly."})

    @app.exception_handler(AIUnavailable)
    @app.exception_handler(OpenAIError)
    async def ai_error(request, error):
        log.error("AI operation failed (%s)", type(error).__name__)
        return JSONResponse(status_code=503, content={"detail": "AI unavailable. Check provider configuration and quota."})

    def reader() -> Reader:
        return app.state.reader

    protected = [Depends(require_session)]

    @app.get("/api/health", response_model=Health)
    def health():
        try:
            app.state.store.health()
            return Health(status="ok", storage="connected")
        except (AzureError, OSError):
            return JSONResponse(status_code=503, content={"status": "degraded", "storage": "unavailable"})

    @app.post("/api/auth/login", response_model=Session)
    def login(payload: LoginRequest, request: Request):
        return issue(request, payload.secret)

    @app.delete("/api/auth/session", response_model=Message)
    def logout(key=Depends(require_session)):
        with app.state.store.writer():
            sessions = app.state.store.read("configuration/sessions.json", {})
            sessions.pop(key, None)
            app.state.store.write("configuration/sessions.json", sessions)
        return Message(message="Signed out")

    @app.get("/api/linkedin/status", response_model=IntegrationStatus, dependencies=protected)
    def linkedin_status():
        identity = app.state.store.read("configuration/linkedin.json", {})
        return IntegrationStatus(
            connected=bool(identity.get("subject") and identity.get("expires_at", 0) > now().timestamp()),
            oauth_available=bool(settings.linkedin_client_id and settings.linkedin_client_secret.get_secret_value()),
            message="LinkedIn identity connection only. Standard permissions do not grant personal home-feed access. Import your authorized LinkedIn export.",
        )

    @app.post("/api/linkedin/connect", response_model=ConnectResponse, dependencies=protected)
    def connect():
        if not settings.linkedin_client_id or not settings.linkedin_client_secret.get_secret_value():
            raise HTTPException(409, "Configure LinkedIn OpenID Connect credentials, or use export import.")
        state = secrets.token_urlsafe(32)
        with app.state.store.writer():
            app.state.store.write("configuration/oauth-state.json", {"hash": digest(state), "expires": now().timestamp() + 600})
        return ConnectResponse(authorization_url="https://www.linkedin.com/oauth/v2/authorization?" + urlencode({
            "response_type": "code", "client_id": settings.linkedin_client_id,
            "redirect_uri": settings.linkedin_redirect_uri, "scope": "openid profile", "state": state,
        }))

    @app.get("/api/linkedin/callback", response_class=HTMLResponse)
    def callback(state: str = "", code: str = "", error: str = ""):
        with app.state.store.writer():
            record = app.state.store.read("configuration/oauth-state.json", {})
            if not secrets.compare_digest(record.get("hash", ""), digest(state)) or record.get("expires", 0) < now().timestamp():
                raise HTTPException(400, "Invalid or expired OAuth state")
            app.state.store.write("configuration/oauth-state.json", {})
        if error or not code:
            raise HTTPException(400, "LinkedIn authorization was not completed")
        try:
            with httpx.Client(timeout=20, follow_redirects=False) as client:
                tokens = client.post("https://www.linkedin.com/oauth/v2/accessToken", data={
                    "grant_type": "authorization_code", "code": code,
                    "client_id": settings.linkedin_client_id,
                    "client_secret": settings.linkedin_client_secret.get_secret_value(),
                    "redirect_uri": settings.linkedin_redirect_uri,
                })
                tokens.raise_for_status()
                payload = tokens.json()
                identity = client.get("https://api.linkedin.com/v2/userinfo", headers={"Authorization": f"Bearer {payload['access_token']}"})
                identity.raise_for_status()
                subject = identity.json()["sub"]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            log.warning("LinkedIn connection failed (%s)", type(exc).__name__)
            raise HTTPException(502, "LinkedIn connection failed. Reconnect from Settings.") from exc
        encrypted = Fernet(encryption_key(settings.session_secret.get_secret_value())).encrypt(payload["access_token"].encode()).decode()
        with app.state.store.writer():
            app.state.store.write("configuration/linkedin.json", {
                "subject": subject, "token_encrypted": encrypted,
                "expires_at": now().timestamp() + int(payload.get("expires_in", 0)),
            })
        return "<html><title>SIGNAL connected</title><body><h1>Identity connected.</h1><p>Return to SIGNAL. Home-feed API access is not available; import an official export from Settings.</p></body></html>"

    @app.post("/api/linkedin/import", response_model=Message, dependencies=protected)
    async def import_export(file: Annotated[UploadFile, File()]):
        data = await file.read(MAX_BYTES + 1)
        await file.close()
        try:
            posts = LinkedInExport().parse(data, file.filename or "")
        except (ValueError, UnicodeError, ValidationError) as exc:
            raise HTTPException(422, "Invalid export: expected UTF-8 Shares.csv, posts.json or ZIP; at most 10 MiB, valid LinkedIn URLs, and up to 10 HTTPS image URLs per post without embedded credentials.") from exc
        count = await asyncio.to_thread(reader().import_posts, posts)
        return Message(message=f"Imported {count} posts. Sync to generate insights.")

    @app.post("/api/linkedin/sync", response_model=SyncStatus, status_code=202, dependencies=protected)
    def sync(background: BackgroundTasks):
        if not app.state.ai.client:
            raise HTTPException(409, "Configure Azure OpenAI or OpenAI before syncing.")
        status = reader().reserve_sync()
        background.add_task(reader().sync)
        return status

    @app.get("/api/linkedin/sync/status", response_model=SyncStatus, dependencies=protected)
    def sync_status():
        return reader().status()

    @app.get("/api/posts/featured", response_model=list[Post], dependencies=protected)
    def featured():
        return sorted(reader().posts(), key=lambda p: (p.insight.relevance_score, p.insight.depth_score), reverse=True)[:5]

    @app.get("/api/posts/recommended", response_model=list[Post], dependencies=protected)
    def recommended():
        preferred = {t.casefold() for t in reader().preferences().preferred_topics}
        return sorted((p for p in reader().posts() if not p.read), key=lambda p: (
            sum(t.casefold() in preferred for t in p.insight.topics), p.insight.relevance_score
        ), reverse=True)[:10]

    @app.get("/api/posts/topics", response_model=list[Topic], dependencies=protected)
    def topics():
        return reader().topics()

    @app.get("/api/posts", response_model=PostPage, dependencies=protected)
    def posts(q: str = Query("", max_length=200), category: str | None = None, topic: str | None = None,
              author: str | None = None, date_from: date | None = None, date_to: date | None = None,
              min_relevance: int = Query(0, ge=0, le=100), read: bool | None = None,
              sort: Literal["relevance", "recency"] = "recency",
              page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
        items = reader().posts()
        if date_from and date_to and date_from > date_to:
            raise HTTPException(422, "date_from must not be after date_to")
        items = [p for p in items if
                 (not q or q.casefold() in (p.original_text + " " + p.insight.title + " " + p.insight.summary + " " + (p.author or "")).casefold())
                 and (not category or category.casefold() == p.insight.category.casefold())
                 and (not topic or topic.casefold() in [t.casefold() for t in p.insight.topics])
                 and (not author or author.casefold() in (p.author or "").casefold())
                 and (not date_from or (p.published_at and p.published_at.date() >= date_from))
                 and (not date_to or (p.published_at and p.published_at.date() <= date_to))
                 and p.insight.relevance_score >= min_relevance and (read is None or p.read == read)]
        items.sort(key=lambda p: p.insight.relevance_score if sort == "relevance" else (p.published_at or p.imported_at).timestamp(), reverse=True)
        return PostPage(items=items[(page - 1) * page_size:page * page_size], total=len(items), page=page, page_size=page_size)

    def find(id):
        post = reader().get(id)
        if not post:
            raise HTTPException(404, "Post not found")
        return post

    @app.get("/api/posts/{id}", response_model=Post, dependencies=protected)
    def detail(id: str):
        return find(id)

    @app.put("/api/posts/{id}/read", response_model=Message, dependencies=protected)
    def mark_read(id: str, payload: ReadRequest):
        with app.state.store.writer():
            find(id)
            state = app.state.store.read("metadata/read-state.json", {})
            state[id] = payload.read
            app.state.store.write("metadata/read-state.json", state)
        return Message(message="Reading state updated")

    @app.post("/api/posts/{id}/explain", response_model=Explanation, dependencies=protected)
    def explain(id: str):
        post = find(id)
        key = f"configuration/explanations/{id}.json"
        cached = app.state.store.read(key)
        if cached:
            return Explanation.model_validate(cached)
        result = app.state.ai.explain(post)
        with app.state.store.writer():
            app.state.store.write(key, result.model_dump(mode="json"))
        return result

    @app.get("/api/bookmarks", response_model=list[Post], dependencies=protected)
    def bookmarks():
        return reader().posts(saved_only=True)

    @app.post("/api/bookmarks/{id}", response_model=Message, dependencies=protected)
    def save(id: str):
        with app.state.store.writer():
            post = find(id)
            saved = app.state.store.read("bookmarks/bookmarks.json", {})
            saved[id] = post.model_dump(mode="json")
            app.state.store.write("bookmarks/bookmarks.json", saved)
        return Message(message="Saved independently of feed retention")

    @app.delete("/api/bookmarks/{id}", response_model=Message, dependencies=protected)
    def unsave(id: str):
        with app.state.store.writer():
            saved = app.state.store.read("bookmarks/bookmarks.json", {})
            saved.pop(id, None)
            app.state.store.write("bookmarks/bookmarks.json", saved)
        return Message(message="Bookmark removed")

    @app.get("/api/statistics", response_model=Statistics, dependencies=protected)
    def statistics():
        return reader().statistics()

    @app.get("/api/settings", response_model=Preferences, dependencies=protected)
    def preferences():
        return reader().preferences()

    @app.put("/api/settings", response_model=Preferences, dependencies=protected)
    def update_preferences(payload: Preferences):
        with app.state.store.writer():
            app.state.store.write("configuration/preferences.json", payload.model_dump(mode="json"))
        return payload

    return app
