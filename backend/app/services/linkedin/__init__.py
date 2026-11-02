import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from typing import Protocol

from app.models import RawPost

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 5000


class ContentSource(Protocol):
    def parse(self, data: bytes, filename: str) -> list[RawPost]: ...


def fingerprint(text: str) -> str:
    return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()


def timestamp(value: str | None) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("Publication timestamps must be strings or null")
    for pattern in (None, "%Y-%m-%d %H:%M:%S", "%m/%d/%y, %I:%M %p", "%m/%d/%Y %H:%M"):
        try:
            date = datetime.fromisoformat(value.replace("Z", "+00:00")) if pattern is None else datetime.strptime(value, pattern)
            # Unknown timezone is not invented. Preserve text; leave timestamp missing.
            if date.tzinfo is None:
                return None
            return date.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


class LinkedInExport:
    """Reads only user-provided exports; never crawls LinkedIn or follows media links."""

    def parse(self, data: bytes, filename: str) -> list[RawPost]:
        if len(data) > MAX_BYTES:
            raise ValueError("Export exceeds 10 MiB")
        if filename.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    members = [item for item in archive.infolist() if item.filename.lower().split("/")[-1] in ("shares.csv", "posts.json")]
                    if not members or sum(item.file_size for item in members) > MAX_BYTES:
                        raise ValueError("ZIP must contain Shares.csv or posts.json, at most 10 MiB expanded")
                    posts = []
                    for item in members:
                        with archive.open(item) as file:
                            content = file.read(MAX_BYTES + 1)
                        posts.extend(self.parse(content, item.filename))
                    if len(posts) > MAX_ROWS:
                        raise ValueError("Export exceeds 5000 posts")
                    return posts
            except zipfile.BadZipFile as error:
                raise ValueError("Invalid ZIP export") from error
        text = data.decode("utf-8-sig")
        if filename.lower().endswith(".json"):
            rows = json.loads(text)
            if isinstance(rows, dict):
                rows = rows.get("posts")
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise ValueError("JSON must contain a posts array")
        elif filename.lower().endswith(".csv"):
            # LinkedIn exports can include a preamble before the CSV header.
            lines = text.splitlines(keepends=True)
            header = next((i for i, line in enumerate(lines) if "sharecommentary" in re.sub(r"[^a-z]", "", line.lower()) or "original_text" in line), None)
            if header is None:
                raise ValueError("CSV needs ShareCommentary or original_text column")
            rows = list(csv.DictReader(io.StringIO("".join(lines[header:]))))
        else:
            raise ValueError("Upload an official Shares.csv, posts.json, or export ZIP")
        if len(rows) > MAX_ROWS:
            raise ValueError("Export exceeds 5000 posts")
        result = []
        now = datetime.now(timezone.utc)
        for row in rows:
            body = row.get("original_text") if "original_text" in row else row.get("ShareCommentary")
            if body is None:
                continue
            if not isinstance(body, str):
                raise ValueError("Post text must be a string")
            if not body.strip():
                continue
            images = row.get("image_urls")
            if images is None:
                # Shares.csv uses MediaUrl; normalized CSV can encode a JSON URL array.
                images = [row["MediaUrl"]] if row.get("MediaUrl") else []
            elif isinstance(images, str):
                images = json.loads(images) if images.strip() else []
            if not isinstance(images, list) or not all(isinstance(url, str) for url in images):
                raise ValueError("image_urls must be an array of HTTPS image URLs")
            # Content-derived IDs deduplicate repeated exports without trusting arbitrary IDs.
            result.append(RawPost(
                id=fingerprint(body), author=row.get("author") or None,
                author_url=row.get("author_url") or None,
                url=row.get("url") or row.get("ShareLink") or None,
                published_at=timestamp(row.get("published_at") or row.get("Date")),
                original_text=body, image_urls=images, imported_at=now,
            ))
        if not result:
            raise ValueError("No post text found in this export")
        return result
