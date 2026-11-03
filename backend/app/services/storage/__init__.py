import json
import logging
import os
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any

from azure.core.exceptions import AzureError, HttpResponseError, ResourceExistsError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobLeaseClient, BlobServiceClient, ContentSettings
from filelock import FileLock, Timeout

from app.config import Settings

log = logging.getLogger(__name__)


class BusyError(Exception):
    pass


class JsonStore:
    """Atomic documents; all writers share one renewable Blob lease or local file lock."""

    def __init__(self, settings: Settings):
        self.root = Path(settings.local_path).resolve()
        self.guard = threading.local()
        self.credential = None
        self.client = None
        self.container = None
        if settings.storage == "azure":
            self.credential = DefaultAzureCredential()
            self.client = BlobServiceClient(
                f"https://{settings.storage_account}.blob.core.windows.net",
                credential=self.credential,
            )
            self.container = self.client.get_container_client(settings.storage_container)
        else:
            self.root.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.root / ".writer.lock")) if not self.container else None

    def close(self):
        if self.client:
            self.client.close()
        if self.credential:
            self.credential.close()

    def _path(self, key: str) -> Path:
        path = PurePosixPath(key)
        if path.is_absolute() or ".." in path.parts or "\\" in key:
            raise ValueError("Invalid storage key")
        result = self.root.joinpath(*path.parts).resolve()
        if not result.is_relative_to(self.root):
            raise ValueError("Invalid storage key")
        return result

    def read(self, key: str, default: Any = None) -> Any:
        if self.container:
            try:
                return json.loads(self.container.download_blob(key).readall())
            except ResourceNotFoundError:
                return default
        path = self._path(key)
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _check_writer(self):
        failed = getattr(self.guard, "failed", None)
        if failed is None:
            raise RuntimeError("Writes require the writer lock")
        if failed.is_set():
            raise BusyError("Storage lease lost; retry operation")

    def write(self, key: str, data: Any):
        self._check_writer()
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        if self.container:
            self.container.upload_blob(
                key, payload.encode(), overwrite=True,
                content_settings=ContentSettings(content_type="application/json"),
            )
            return
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temp.open("w", encoding="utf-8") as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def keys(self, prefix: str) -> list[str]:
        if self.container:
            return sorted(item.name for item in self.container.list_blobs(name_starts_with=prefix))
        directory = self._path(prefix)
        if not directory.exists():
            return []
        return sorted(path.relative_to(self.root).as_posix() for path in directory.rglob("*.json"))

    def delete(self, key: str):
        self._check_writer()
        if not key.startswith(("linkedin/raw/", "linkedin/processed/")) or not key.endswith(".json"):
            raise ValueError("Deletion is restricted to feed JSON")
        if self.container:
            try:
                self.container.delete_blob(key)
            except ResourceNotFoundError:
                return
        else:
            self._path(key).unlink(missing_ok=True)
        log.info("Deleted expired feed document %s", key)

    def health(self):
        if self.container:
            self.container.get_container_properties()
        else:
            list(self.root.iterdir())

    @contextmanager
    def writer(self):
        with self.lease("writer") as failed:
            self.guard.failed = failed
            try:
                yield
                self._check_writer()
            finally:
                self.guard.failed = None

    @contextmanager
    def lease(self, name: str):
        if name not in ("writer", "crawler"):
            raise ValueError("Unknown storage lease")
        lease = None
        stop = threading.Event()
        failed = threading.Event()
        renewal = None
        acquired = False
        lock = self.lock if name == "writer" else FileLock(str(self.root / ".crawler.lock"))
        try:
            if self.container:
                blob = self.container.get_blob_client(f"metadata/{name}-lock.json")
                try:
                    blob.upload_blob(b"{}", overwrite=False)
                except ResourceExistsError:
                    pass
                lease = BlobLeaseClient(blob)
                try:
                    lease.acquire(lease_duration=60)
                except HttpResponseError as error:
                    if error.status_code == 409:
                        raise BusyError("Another operation is running") from error
                    raise
                acquired = True

                def renew():
                    while not stop.wait(10):
                        try:
                            lease.renew()
                        except AzureError as error:
                            log.error("%s lease renewal failed (%s)", name, type(error).__name__)
                            failed.set()
                            return

                renewal = threading.Thread(target=renew, daemon=True)
                renewal.start()
            else:
                try:
                    lock.acquire(timeout=2)
                    acquired = True
                except Timeout as error:
                    raise BusyError("Another operation is running") from error
            yield failed
            if failed.is_set():
                raise BusyError("Storage lease lost; retry operation")
        finally:
            stop.set()
            if renewal:
                renewal.join(timeout=30)
            if acquired and lease:
                try:
                    lease.release()
                except AzureError as error:
                    log.error("%s lease release failed (%s)", name, type(error).__name__)
            elif acquired:
                lock.release()
