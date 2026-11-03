import argparse
import logging
import time

from app.config import get_settings
from app.models import CrawlStatus
from app.services.ai import Intelligence
from app.services.linkedin.crawler import CrawlError, CrawlerSettings, LinkedInCrawler
from app.services.reader import Reader, now
from app.services.storage import BusyError, JsonStore

log = logging.getLogger("signal.crawler")
STATUS_KEY = "metadata/last-crawl.json"


def run_worker(reader: Reader, options: CrawlerSettings, crawler=None, *, resume=False) -> CrawlStatus:
    store = reader.store
    with store.lease("crawler") as lease_lost:
        previous = CrawlStatus.model_validate(store.read(STATUS_KEY, {}))
        if options.enabled and previous.status == "action_required" and not resume:
            log.warning("Collection paused: explicit --resume required after account action")
            return previous
        status = CrawlStatus(
            enabled=options.enabled, status="running" if options.enabled else "disabled",
            started_at=now(), last_success_at=previous.last_success_at,
            code="collecting" if options.enabled else "disabled",
            message="Collecting a bounded LinkedIn feed batch." if options.enabled else "Background collection is disabled.",
        )

        def persist():
            with store.writer():
                if lease_lost.is_set():
                    raise BusyError("Crawl lease was lost")
                store.write(STATUS_KEY, status.model_dump(mode="json"))

        persist()
        try:
            if not options.enabled:
                return status
            if not reader.ai.client:
                raise CrawlError("ai_not_configured", action_required=True)
            log.info("Starting bounded collection")
            result = (crawler or LinkedInCrawler(options)).collect()
            if lease_lost.is_set():
                raise BusyError("Crawl lease was lost")
            reader.import_posts(result.posts)
            status.extracted = len(result.posts)
            status.skipped = result.skipped
            status.limit_reached = result.limit_reached
            # Processing must run even when the app's export scheduler is set to manual.
            processing_deadline = time.monotonic() + options.processing_max_seconds
            for _ in range(options.max_processing_batches):
                if lease_lost.is_set():
                    raise BusyError("Crawl lease was lost")
                reader.reserve_sync()
                reader.sync(deadline=processing_deadline)
                processing = reader.status()
                if processing.status != "completed":
                    raise CrawlError("processing_failed")
                if not processing.remaining:
                    break
                if time.monotonic() >= processing_deadline:
                    break
                if not processing.imported:
                    raise CrawlError("processing_stalled")
            status.status = "completed"
            status.last_success_at = now()
            status.code = "completed"
            status.message = (
                f"Collected {status.extracted} posts; skipped {status.skipped} unsupported cards. "
                f"Processing finished; {reader.status().remaining} posts pending. "
                "Feed coverage is best effort, not exhaustive."
            )
        except CrawlError as error:
            status.status = "action_required" if error.action_required else "failed"
            status.code = error.code
            status.message = (
                f"Collection stopped ({error.code}). Resolve account/configuration issues securely, then run with --resume."
                if error.action_required else
                f"Collection failed ({error.code}). Retained raw posts can be retried."
            )
            log.warning("Collection stopped (%s)", error.code)
        except BusyError:
            status.status = "failed"
            status.code = "storage_busy"
            status.message = "Storage is busy or its lease was lost. Retry on the next scheduled run."
            log.warning("Collection interrupted: storage lease unavailable")
        except Exception as error:
            # Browser exceptions can contain form values/HTML. Never log exception text or traces.
            status.status = "failed"
            status.code = "worker_error"
            status.message = "Background collection failed. Check browser installation, connectivity and storage; retained posts can be retried."
            log.error("Collection failed (%s)", type(error).__name__)
        finally:
            status.finished_at = now()
            if not lease_lost.is_set():
                persist()
        return status


def main() -> int:
    parser = argparse.ArgumentParser(description="SIGNAL bounded background LinkedIn worker")
    parser.add_argument("--resume", action="store_true", help="Retry after manually resolving an account/configuration challenge")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    store = None
    ai = None
    try:
        settings = get_settings()
        options = CrawlerSettings()
        store = JsonStore(settings)
        ai = Intelligence(settings)
        status = run_worker(Reader(store, ai), options, resume=args.resume)
        log.info("Worker result: %s (%s)", status.status, status.code)
        return 0 if status.status in ("completed", "disabled") else 1
    except BusyError:
        log.warning("Worker could not acquire or retain its lease; retry on the next run")
        return 1
    except Exception as error:
        log.error("Worker could not initialize (%s)", type(error).__name__)
        return 1
    finally:
        if ai:
            ai.close()
        if store:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
