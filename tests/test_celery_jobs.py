import os

import pytest

pytest.importorskip("celery")

os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "1")

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from graphmovie import api
from graphmovie.celery_app import enable_eager_mode
from graphmovie.jobs import enqueue_plan, enqueue_resume, get_job
from graphmovie.service import MovieService
from graphmovie.state import MovieRequest
from graphmovie.store import SqliteProjectStore


@pytest.fixture()
def service(tmp_path, monkeypatch):
    enable_eager_mode()

    store = SqliteProjectStore(tmp_path / "projects.sqlite")
    svc = MovieService(checkpointer=MemorySaver(), store=store)
    monkeypatch.setattr(api, "_service", svc)

    def _build():
        return svc

    monkeypatch.setattr("graphmovie.tasks._service", _build)
    monkeypatch.setattr("graphmovie.service.build_service", _build)
    return svc


def test_enqueue_plan_and_resume_eager(service, tmp_path):
    request = MovieRequest(
        title="雨夜霓虹",
        genre="科幻",
        style="cinematic",
        duration_sec=45,
        budget_cny=25000,
        footage_source="generated",
    )
    queued = enqueue_plan(request.model_dump())
    assert queued["status"] == "queued"
    assert queued["task_id"]

    done = get_job(queued["task_id"])
    assert done["status"] == "SUCCESS"
    assert done["result"]["status"] == "interrupted"
    project_id = done["result"]["project_id"]

    resume_queued = enqueue_resume(project_id, decision="approve")
    resume_done = get_job(resume_queued["task_id"])
    assert resume_done["status"] == "SUCCESS"
    assert resume_done["result"]["status"] == "approved"


def test_jobs_api_eager(service):
    client = TestClient(api.app)
    created = client.post(
        "/jobs/plan",
        json={
            "title": "雨夜霓虹",
            "genre": "科幻",
            "style": "cinematic",
            "duration_sec": 45,
            "budget_cny": 25000,
            "footage_source": "generated",
        },
    )
    assert created.status_code == 202
    body = created.json()
    task_id = body["task_id"]
    project_id = body["project_id"]

    status = client.get(f"/jobs/{task_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "SUCCESS"
    assert status.json()["result"]["status"] == "interrupted"

    resumed = client.post(
        f"/jobs/{project_id}/resume",
        json={"decision": "approve"},
    )
    assert resumed.status_code == 202
    resume_status = client.get(f"/jobs/{resumed.json()['task_id']}")
    assert resume_status.json()["status"] == "SUCCESS"
    assert resume_status.json()["result"]["status"] == "approved"
