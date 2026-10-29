import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from graphmovie import api
from graphmovie.config import Settings
from graphmovie.runtime_guards import SharedCheckpointerRequired, require_shared_checkpointer
from graphmovie.security import ApiKeyMiddleware, RateLimitMiddleware
from graphmovie.service import MovieService
from graphmovie.store import SqliteProjectStore


@pytest.fixture()
def service(tmp_path, monkeypatch):
    store = SqliteProjectStore(tmp_path / "projects.sqlite")
    svc = MovieService(checkpointer=MemorySaver(), store=store)
    monkeypatch.setattr(api, "_service", svc)
    return svc


def test_api_key_required_when_configured(monkeypatch):
    from graphmovie import security

    monkeypatch.setattr(
        security,
        "settings",
        Settings(
            api_keys=frozenset({"secret-key"}),
            rate_limit_per_minute=0,
            request_timeout_sec=0,
        ),
    )
    app = FastAPI()
    app.add_middleware(ApiKeyMiddleware)

    @app.get("/secure")
    def secure() -> dict[str, str]:
        return {"ok": "1"}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/secure").status_code == 401
    assert client.get("/secure", headers={"X-API-Key": "secret-key"}).status_code == 200


def test_rate_limit_middleware(monkeypatch):
    from graphmovie import security

    monkeypatch.setattr(
        security,
        "settings",
        Settings(api_keys=frozenset(), rate_limit_per_minute=2, request_timeout_sec=0),
    )
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, per_minute=2)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "1"}

    client = TestClient(app)
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 429


def test_require_shared_checkpointer_blocks_non_eager(monkeypatch):
    monkeypatch.setattr(
        "graphmovie.runtime_guards.settings",
        Settings(database_url=None, celery_task_always_eager=False),
    )
    with pytest.raises(SharedCheckpointerRequired):
        require_shared_checkpointer(operation="resume_project")


def test_require_shared_checkpointer_allows_eager(monkeypatch):
    monkeypatch.setattr(
        "graphmovie.runtime_guards.settings",
        Settings(database_url=None, celery_task_always_eager=True),
    )
    require_shared_checkpointer(operation="resume_project")


def test_health_reports_product_boundary(service):
    client = TestClient(api.app)
    body = client.get("/health").json()
    assert body["product"] == "storyboard_planning"
