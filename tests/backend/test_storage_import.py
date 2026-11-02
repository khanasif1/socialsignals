import csv
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.linkedin import LinkedInExport, MAX_BYTES, fingerprint
from app.services.storage import JsonStore


def test_csv_preamble_missing_fields_and_timezone():
    data = b'LinkedIn export\nDate,ShareCommentary,ShareLink\n2026-11-02 12:00:00,"RAG with source evaluation",\n'
    post = LinkedInExport().parse(data, "Shares.csv")[0]
    assert post.author is None
    assert post.published_at is None
    assert post.url is None
    assert post.image_urls == []


def test_source_images_from_json_csv_and_zip():
    urls = ["https://media.licdn.com/dms/image/example-one.jpg", "https://media.licdn.com/dms/image/example-two.png?view=original"]
    post = LinkedInExport().parse(json.dumps([{"original_text": "Original image post", "image_urls": [*urls, urls[0]]}]).encode(), "posts.json")[0]
    assert [str(url) for url in post.image_urls] == urls
    csv_file = io.StringIO(newline="")
    writer = csv.writer(csv_file)
    writer.writerow(["ShareCommentary", "MediaUrl"])
    writer.writerow(["Original image post", urls[0]])
    post = LinkedInExport().parse(csv_file.getvalue().encode(), "Shares.csv")[0]
    assert [str(url) for url in post.image_urls] == urls[:1]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Shares.csv", csv_file.getvalue())
    assert LinkedInExport().parse(buffer.getvalue(), "export.zip")[0].image_urls == post.image_urls
    csv_file = io.StringIO(newline="")
    writer = csv.writer(csv_file)
    writer.writerow(["original_text", "image_urls"])
    writer.writerow(["Original image post", json.dumps(urls)])
    post = LinkedInExport().parse(csv_file.getvalue().encode(), "posts.csv")[0]
    assert [str(url) for url in post.image_urls] == urls


@pytest.mark.parametrize("images", [
    "https://media.licdn.com/image.jpg", [42], {},
    ["http://media.licdn.com/image.jpg"], ["javascript:alert(1)"],
    ["data:image/png;base64,abc"], ["file:///private/image.png"],
    ["https://member:password@media.licdn.com/image.jpg"],
    [f"https://media.licdn.com/{index}.jpg" for index in range(11)],
])
def test_invalid_source_images_are_rejected(images):
    with pytest.raises(ValueError):
        LinkedInExport().parse(json.dumps([{"original_text": "Image post", "image_urls": images}]).encode(), "posts.json")


def test_zip_only_reads_posts():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Shares.csv", 'Date,ShareCommentary,ShareLink\n,"MCP tool design",\n')
        archive.writestr("../../credentials.txt", "never extracted")
    assert len(LinkedInExport().parse(buffer.getvalue(), "export.zip")) == 1


def test_malformed_and_oversized_exports():
    for data, name in [
        (b"[]", "posts.json"), (b"{}", "posts.json"), (b"bad", "bad.zip"),
        (b"x" * (MAX_BYTES + 1), "posts.json"),
        (b'[{"original_text":42}]', "posts.json"),
        (b'[{"original_text":"RAG","published_at":42}]', "posts.json"),
    ]:
        with pytest.raises(ValueError):
            LinkedInExport().parse(data, name)
    assert fingerprint(" Hello  WORLD ") == fingerprint("hello world")


def test_safe_paths_and_protected_deletion(application):
    store = application.state.store
    with pytest.raises(ValueError):
        store.read("../outside.json")
    with pytest.raises(RuntimeError):
        store.write("configuration/settings.json", {})
    with store.writer(), pytest.raises(ValueError):
        store.delete("bookmarks/bookmarks.json")


def test_atomic_writes_across_store_instances(application):
    settings = application.state.settings

    def increment(_):
        store = JsonStore(settings)
        with store.writer():
            state = store.read("metadata/counter.json", {"count": 0})
            state["count"] += 1
            store.write("metadata/counter.json", state)
        store.close()

    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(increment, range(20)))
    assert application.state.store.read("metadata/counter.json") == {"count": 20}
