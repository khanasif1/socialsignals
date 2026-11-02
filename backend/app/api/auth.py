import base64
import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models import Session
from app.services.reader import now

bearer = HTTPBearer(auto_error=False)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def issue(request: Request, secret: str) -> Session:
    store = request.app.state.store
    settings = request.app.state.settings
    with store.writer():
        # A shared single-user limiter works across App Service instances.
        attempts = store.read("configuration/auth-attempts.json", [])
        attempts = [t for t in attempts if t > now().timestamp() - 300]
        if len(attempts) >= 10:
            raise HTTPException(429, "Too many login attempts. Try again in five minutes.")
        if not hmac.compare_digest(digest(secret), digest(settings.login_secret.get_secret_value())):
            attempts.append(now().timestamp())
            store.write("configuration/auth-attempts.json", attempts)
            raise HTTPException(401, "Invalid passphrase")
        store.write("configuration/auth-attempts.json", [])
        token = secrets.token_urlsafe(48)
        expiry = now() + timedelta(days=7)
        sessions = store.read("configuration/sessions.json", {})
        sessions = {k: v for k, v in sessions.items() if v > now().timestamp()}
        sessions[digest(token)] = expiry.timestamp()
        store.write("configuration/sessions.json", sessions)
    return Session(token=token, expires_at=expiry)


def require_session(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    if not credentials:
        raise HTTPException(401, "Sign in to SIGNAL", headers={"WWW-Authenticate": "Bearer"})
    key = digest(credentials.credentials)
    sessions = request.app.state.store.read("configuration/sessions.json", {})
    if sessions.get(key, 0) <= now().timestamp():
        raise HTTPException(401, "Session expired. Sign in again.", headers={"WWW-Authenticate": "Bearer"})
    return key


def encryption_key(secret: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
