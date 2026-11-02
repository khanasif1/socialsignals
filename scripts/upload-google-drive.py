"""Official Drive v3 resumable upload; credentials are read from the environment only."""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def upload(path: Path):
    token = os.environ["GOOGLE_DRIVE_ACCESS_TOKEN"]
    metadata = json.dumps({
        "name": path.name, "parents": [os.environ["GOOGLE_DRIVE_FOLDER_ID"]],
        "description": "Private signed SIGNAL iOS build. Apple device provisioning restrictions apply.",
    }).encode()
    request = urllib.request.Request(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&fields=id,webViewLink",
        data=metadata, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "X-Upload-Content-Type": "application/octet-stream", "X-Upload-Content-Length": str(path.stat().st_size)},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        location = response.headers["Location"]
    parsed = urlparse(location)
    if parsed.scheme != "https" or parsed.hostname not in ("www.googleapis.com", "content.googleapis.com"):
        raise ValueError("Unexpected Drive upload host")
    # Upload chunks so a large IPA is not loaded into memory.
    size = path.stat().st_size
    offset = 0
    result = None
    with path.open("rb") as file:
        while chunk := file.read(8 * 1024 * 1024):
            end = offset + len(chunk) - 1
            request = urllib.request.Request(location, data=chunk, method="PUT", headers={
                "Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream",
                "Content-Length": str(len(chunk)), "Content-Range": f"bytes {offset}-{end}/{size}",
            })
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    result = json.load(response)
            except urllib.error.HTTPError as error:
                if error.code != 308:
                    raise
            offset = end + 1
    if not result or "id" not in result:
        raise RuntimeError("Drive upload did not finish; no completion response received")
    print(f"Uploaded privately: {result.get('webViewLink', result['id'])}")


if __name__ == "__main__":
    try:
        upload(Path(sys.argv[1]))
    except urllib.error.HTTPError as error:
        sys.exit(f"Drive upload failed (HTTP {error.code}); verify token scope and folder permissions.")
