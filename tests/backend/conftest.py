import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.config import Settings
from app.main import create_app
from app.models import Explanation, Insight


class FakeAI:
    client = True
    fail = False

    def analyze(self, post, preferences, candidates=None):
        if self.fail:
            raise RuntimeError("Simulated provider outage")
        return Insight(
            title=post.original_text[:80], category="AI Architecture", topics=["RAG", "Agentic AI"],
            summary="Source-grounded summary", main_insight="Evaluate retrieval separately.",
            patterns=["Evaluation loop"], technologies=["RAG"], practical_relevance="Measure source recall.",
            why_it_matters="Find failures.", depth_score=90, relevance_score=95, tags=["evaluation"],
        )

    def explain(self, post):
        return Explanation(executive="Overview", architect="Architecture", technical="Technical")

    def close(self):
        pass


@pytest.fixture
def application(tmp_path):
    settings = Settings(
        _env_file=None, login_secret="test-login-passphrase-with-32-characters",
        session_secret="independent-test-secret-with-32-characters",
        local_path=str(tmp_path), scheduler_enabled=False,
        linkedin_client_id="test-client", linkedin_client_secret="test-secret",
    )
    return create_app(settings, ai=FakeAI())


@pytest.fixture
def client(application):
    with TestClient(application) as client:
        yield client


@pytest.fixture
def auth(client):
    result = client.post("/api/auth/login", json={"secret": "test-login-passphrase-with-32-characters"})
    assert result.status_code == 200
    return {"Authorization": f"Bearer {result.json()['token']}"}


@pytest.fixture
def post_data():
    return {"original_text": "RAG systems need independent retrieval and generation evaluation.",
            "author": "Authorized Author", "url": "https://www.linkedin.com/feed/update/urn:li:activity:123",
            "published_at": "2026-11-02T00:00:00Z"}
