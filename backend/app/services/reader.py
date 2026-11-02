import logging
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from app.models import Post, Preferences, RawPost, Statistics, SyncStatus, Topic
from app.services.ai import Intelligence
from app.services.storage import BusyError, JsonStore

log = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc)


class Reader:
    def __init__(self, store: JsonStore, ai: Intelligence):
        self.store = store
        self.ai = ai

    def preferences(self) -> Preferences:
        return Preferences.model_validate(self.store.read("configuration/preferences.json", {}))

    def status(self) -> SyncStatus:
        return SyncStatus.model_validate(self.store.read("metadata/last-sync.json", {}))

    def posts(self, saved_only=False) -> list[Post]:
        saved = self.store.read("bookmarks/bookmarks.json", {})
        reads = self.store.read("metadata/read-state.json", {})
        documents = {}
        if not saved_only:
            for key in self.store.keys("linkedin/processed/"):
                for post in self.store.read(key, []):
                    documents[post["id"]] = post
        documents.update(saved)
        posts = []
        for id, data in documents.items():
            post = Post.model_validate(data)
            post.saved = id in saved
            post.read = reads.get(id, False)
            posts.append(post)
        return posts

    def get(self, id: str) -> Post | None:
        return next((post for post in self.posts() if post.id == id), None)

    def topics(self) -> list[Topic]:
        groups = {}
        for post in self.posts():
            for topic in set(post.insight.topics):
                groups.setdefault(topic, []).append(post)
        return [
            Topic(name=name, count=len(posts),
                  latest=max((p.published_at for p in posts if p.published_at), default=None),
                  featured=max(posts, key=lambda p: p.insight.relevance_score))
            for name, posts in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
        ]

    def statistics(self) -> Statistics:
        posts = self.posts()
        state = self.store.read("metadata/ingestion-state.json", {})
        return Statistics(
            total_posts=state.get("total_extracted", 0), relevant_posts=len(posts),
            unread_posts=sum(not post.read for post in posts),
            by_topic=dict(Counter(topic for post in posts for topic in set(post.insight.topics))),
            by_author=dict(Counter(post.author or "Unknown author" for post in posts)),
            latest_sync=self.status(),
        )

    def import_posts(self, posts: list[RawPost]):
        with self.store.writer():
            state = self.store.read("metadata/ingestion-state.json", {"seen": {}, "total_extracted": 0})
            state["total_extracted"] += len({p.id for p in posts if p.id not in state["seen"]})
            for post in posts:
                state["seen"].setdefault(post.id, {"done": False, "date": now().date().isoformat()})
            images = {p.id: p.model_dump(mode="json")["image_urls"] for p in posts if p.image_urls}
            if images:
                for processed_key in self.store.keys("linkedin/processed/"):
                    documents = self.store.read(processed_key, [])
                    changed = False
                    for document in documents:
                        if document["id"] in images and document.get("image_urls") != images[document["id"]]:
                            document["image_urls"] = images[document["id"]]
                            changed = True
                    if changed:
                        self.store.write(processed_key, documents)
                bookmarks = self.store.read("bookmarks/bookmarks.json", {})
                changed = False
                for id, urls in images.items():
                    if id in bookmarks and bookmarks[id].get("image_urls") != urls:
                        bookmarks[id]["image_urls"] = urls
                        changed = True
                if changed:
                    self.store.write("bookmarks/bookmarks.json", bookmarks)
            key = f"linkedin/raw/{now().date().isoformat()}/{uuid.uuid4().hex}.json"
            self.store.write(key, [p.model_dump(mode="json") for p in posts])
            self.store.write("metadata/ingestion-state.json", state)
        return len(posts)

    def reserve_sync(self) -> SyncStatus:
        with self.store.writer():
            status = self.status()
            if status.status == "running":
                # Active workers hold the writer lease. Allow abandoned reservations to recover.
                if status.started_at and now() - status.started_at < timedelta(minutes=2):
                    raise BusyError("A sync is already running")
            status = SyncStatus(status="running", started_at=now(), message="Processing uploaded LinkedIn exports.")
            self.store.write("metadata/last-sync.json", status.model_dump(mode="json"))
            return status

    def sync(self):
        with self.store.writer():
            status = self.status()
            preferences = self.preferences()
            state = self.store.read("metadata/ingestion-state.json", {"seen": {}, "total_extracted": 0})
            pending = {}
            for key in self.store.keys("linkedin/raw/"):
                for data in self.store.read(key, []):
                    if not state["seen"].get(data["id"], {}).get("done", False):
                        raw = RawPost.model_validate(data)
                        if data["id"] in pending:
                            status.duplicates += 1
                            if not raw.image_urls:
                                raw.image_urls = pending[data["id"]].image_urls
                        pending[data["id"]] = raw
            selected = list(pending.values())[:preferences.max_posts_per_sync]
            try:
                existing = self.posts()
                for raw in selected:
                    candidates = [{"id": p.id, "summary": p.insight.summary[:250]} for p in existing[-50:]]
                    insight = self.ai.analyze(raw, preferences, candidates)
                    candidate_ids = {p["id"] for p in candidates}
                    duplicate = insight.duplicate_of in candidate_ids
                    if insight.duplicate_of and not duplicate:
                        raise ValueError("AI returned an unknown duplicate reference")
                    if duplicate:
                        status.duplicates += 1
                    elif insight.relevance_score >= preferences.min_relevance_score:
                        post = Post(**raw.model_dump(), insight=insight, generation="llm")
                        key = f"linkedin/processed/{raw.imported_at.date().isoformat()}/{raw.id}.json"
                        self.store.write(key, [post.model_dump(mode="json")])
                        existing.append(post)
                        status.relevant += 1
                    state["seen"][raw.id] = {"done": True, "date": raw.imported_at.date().isoformat()}
                    self.store.write("metadata/ingestion-state.json", state)
                    status.imported += 1
                    self.store.write("metadata/last-sync.json", status.model_dump(mode="json"))
                status.status = "completed"
                status.remaining = len(pending) - len(selected)
                status.message = "Export processed." if pending else "No new exported posts. Upload an export; LinkedIn home-feed retrieval is not available."
            except Exception as error:
                # Fail visibly, retaining raw data and completed records for a safe retry.
                log.error("Sync failed (%s); raw data retained", type(error).__name__)
                status.status = "failed"
                status.remaining = len(pending) - status.imported
                status.message = "Processing failed. Check AI configuration, quota and server logs; uploaded data is retained for retry."
            status.finished_at = now()
            self.store.write("metadata/last-sync.json", status.model_dump(mode="json"))
            self.store.write("metadata/statistics.json", self.statistics().model_dump(mode="json"))
            self.store.write("exports/daily-summary.json", {
                "generated_at": now().isoformat(),
                "post_ids": [p.id for p in sorted(self.posts(), key=lambda p: p.insight.relevance_score, reverse=True)[:10]],
            })
        self.cleanup()

    def cleanup(self):
        with self.store.writer():
            cutoff = now().date() - timedelta(days=self.preferences().retention_days)
            for prefix in ("linkedin/raw/", "linkedin/processed/"):
                for key in self.store.keys(prefix):
                    date = datetime.strptime(key.split("/")[2], "%Y-%m-%d").date()
                    if date <= cutoff:
                        self.store.delete(key)

    def scheduled_tick(self):
        try:
            self.cleanup()
            frequency = self.preferences().sync_frequency
            last = self.status()
            interval = {"hourly": 3600, "daily": 86400}.get(frequency)
            abandoned = last.status == "running" and last.started_at and now() - last.started_at >= timedelta(minutes=2)
            if interval and (last.status != "running" or abandoned) and (
                not last.finished_at or (now() - last.finished_at).total_seconds() >= interval
            ):
                self.reserve_sync()
                self.sync()
        except BusyError:
            log.info("Scheduled maintenance skipped: active writer")
        except Exception as error:
            log.error("Scheduled maintenance failed (%s)", type(error).__name__)
