from __future__ import annotations

from typing import Any


class WorkerUnavailableError(RuntimeError):
    """Raised when Celery extras are not installed."""


def enqueue_plan(request_payload: dict[str, Any]) -> dict[str, str]:
    try:
        from graphmovie.tasks import plan_project
    except ImportError as exc:  # pragma: no cover
        raise WorkerUnavailableError(
            "Celery worker extras are not installed. Run: uv sync --extra worker"
        ) from exc
    async_result = plan_project.delay(request_payload)
    return {
        "task_id": async_result.id,
        "task": "plan_project",
        "status": "queued",
    }


def enqueue_resume(
    project_id: str,
    *,
    decision: str = "approve",
    notes: str | None = None,
) -> dict[str, str]:
    try:
        from graphmovie.tasks import resume_project
    except ImportError as exc:  # pragma: no cover
        raise WorkerUnavailableError(
            "Celery worker extras are not installed. Run: uv sync --extra worker"
        ) from exc
    async_result = resume_project.delay(project_id, decision=decision, notes=notes)
    return {
        "task_id": async_result.id,
        "task": "resume_project",
        "project_id": project_id,
        "status": "queued",
    }


def get_job(task_id: str) -> dict[str, Any]:
    try:
        from graphmovie.celery_app import celery_app
    except ImportError as exc:  # pragma: no cover
        raise WorkerUnavailableError(
            "Celery worker extras are not installed. Run: uv sync --extra worker"
        ) from exc

    async_result = celery_app.AsyncResult(task_id)
    payload: dict[str, Any] = {
        "task_id": task_id,
        "status": async_result.status,
    }
    if async_result.successful():
        payload["result"] = async_result.result
    elif async_result.failed():
        payload["error"] = str(async_result.result)
    elif async_result.status == "STARTED" and async_result.info:
        payload["meta"] = async_result.info
    return payload
