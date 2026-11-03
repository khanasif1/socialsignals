"""Verify the deployed API using one explicitly synthetic, retained sample post."""

import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx


TEXT = """[SYNTHETIC DEPLOYMENT VERIFICATION - not a LinkedIn post]
An Azure RAG service can separate retrieval evaluation from answer evaluation.
Measure retrieval recall on a labeled question set before changing prompts.
Record document versions and trace IDs so failed answers can be reproduced.
Use managed identity rather than API keys for Azure OpenAI and Blob Storage.
Give the application only its resource-scoped data-plane roles. Retry transient
throttling with bounded backoff and retain original source text for inspection.
This fictional sample verifies SIGNAL's deployed storage and AI pipeline."""


def verify(parameters_path: Path, outputs_path: Path):
    parameters = json.loads(parameters_path.read_text(encoding="utf-8-sig"))
    outputs = json.loads(outputs_path.read_text(encoding="utf-8-sig"))
    url = outputs["applicationUrl"]["value"]
    target = urlparse(url)
    if target.scheme != "https" or not target.hostname or target.username or target.password:
        raise ValueError("Deployment output must contain an HTTPS application URL.")
    post_id = hashlib.sha256(" ".join(TEXT.casefold().split()).encode()).hexdigest()

    with httpx.Client(base_url=url, timeout=180, follow_redirects=False) as client:
        def request(method, path, **kwargs):
            response = client.request(method, f"/api{path}", **kwargs)
            response.raise_for_status()
            return response.json()

        health = request("GET", "/health")
        assert health == {"status": "ok", "storage": "connected", "worker_image": True}
        assert client.get("/api/posts").status_code == 401
        session = request("POST", "/auth/login", json={"secret": parameters["parameters"]["loginSecret"]["value"]})
        client.headers["Authorization"] = f"Bearer {session['token']}"
        try:
            fixture = [{"author": "SIGNAL verification (synthetic)", "original_text": TEXT}]
            request("POST", "/linkedin/import", files={
                "file": ("posts.json", json.dumps(fixture).encode(), "application/json"),
            })
            request("POST", "/linkedin/sync")
            for _ in range(90):
                status = request("GET", "/linkedin/sync/status")
                if status["status"] != "running":
                    break
                time.sleep(2)
            assert status["status"] == "completed", f"AI processing did not complete: {status['status']}"
            post = request("GET", f"/posts/{post_id}")
            assert post["original_text"] == TEXT and post["generation"] == "llm"
            assert post["url"] is None and post["author"] == fixture[0]["author"]
            assert post["insight"]["title"] and post["insight"]["summary"]
            request("POST", f"/bookmarks/{post_id}")
            request("PUT", f"/posts/{post_id}/read", json={"read": True})
            saved = request("GET", "/bookmarks")
            assert any(item["id"] == post_id and item["saved"] and item["read"] for item in saved)
            explanation = request("POST", f"/posts/{post_id}/explain")
            assert explanation["generated"] and all(explanation[key] for key in ("executive", "architect", "technical"))
            assert any(item["id"] == post_id for item in request("GET", "/posts", params={"q": "SYNTHETIC"})["items"])
            integration = request("GET", "/linkedin/status")
            return {
                "application_url": url, "storage": health["storage"],
                "worker_image": health["worker_image"], "ai_generation": post["generation"],
                "original_text_preserved": True, "saved": True, "read": True,
                "explanation_generated": True, "search_verified": True,
                "crawler_enabled": integration["crawler"]["enabled"],
                "sample_id": post_id, "sample_is_synthetic": True,
                "sample_retained": True,
            }
        finally:
            request("DELETE", "/auth/session")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameters", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.parameters, args.outputs)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
