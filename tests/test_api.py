from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from graphmovie import api
from graphmovie.service import MovieService
from graphmovie.store import SqliteProjectStore


def test_api_create_resume_export(tmp_path, monkeypatch):
    store = SqliteProjectStore(tmp_path / "projects.sqlite")
    service = MovieService(checkpointer=MemorySaver(), store=store)
    monkeypatch.setattr(api, "_service", service)
    client = TestClient(api.app)

    created = client.post(
        "/projects",
        json={
            "title": "雨夜霓虹",
            "genre": "科幻",
            "style": "cinematic",
            "duration_sec": 45,
            "budget_cny": 25000,
            "footage_source": "generated",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "interrupted"
    project_id = body["project_id"]

    resumed = client.post(
        f"/projects/{project_id}/resume",
        json={"decision": "approve"},
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "approved"

    exported = client.get(f"/projects/{project_id}/export?format=markdown")
    assert exported.status_code == 200
    assert "雨夜霓虹" in exported.text
