from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.services.linkedin import MAX_BYTES


class UploadLimit:
    """Bound multipart traffic, including native clients using chunked uploads."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != "/api/linkedin/import":
            await self.app(scope, receive, send)
            return
        limit = MAX_BYTES + 65536
        headers = dict(scope["headers"])
        length = headers.get(b"content-length", b"")
        if length.isdigit() and int(length) > limit:
            await JSONResponse(status_code=413, content={"detail": "Export exceeds 10 MiB"})(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > limit:
                await JSONResponse(status_code=413, content={"detail": "Export exceeds 10 MiB"})(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
