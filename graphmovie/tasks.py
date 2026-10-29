from __future__ import annotations

from typing import Any

from graphmovie.celery_app import celery_app
from graphmovie.service import build_service
from graphmovie.state import MovieRequest


def _service():
    # Build per task so worker processes pick up current env/checkpointer.
    return build_service()


@celery_app.task(name="graphmovie.tasks.plan_project", bind=True)
def plan_project(self, request_payload: dict[str, Any]) -> dict[str, Any]:
    """Run LangGraph planning in a worker process."""
    self.update_state(
        state="STARTED",
        meta={"stage": "planning", "project_id": request_payload.get("project_id")},
    )
    request = MovieRequest.model_validate(request_payload)
    result = _service().create(request)
    return {
        "task": "plan_project",
        "project_id": result.get("project_id") or request.project_id,
        "status": result.get("status"),
        "result": result,
    }


@celery_app.task(name="graphmovie.tasks.resume_project", bind=True)
def resume_project(
    self,
    project_id: str,
    decision: str = "approve",
    notes: str | None = None,
) -> dict[str, Any]:
    """Resume human review in a worker process.

    Requires a shared checkpointer (DATABASE_URL / PostgresSaver) when the
    API process and worker are separate. Eager mode shares one process memory.
    """
    self.update_state(
        state="STARTED",
        meta={"stage": "resuming", "project_id": project_id, "decision": decision},
    )
    result = _service().resume(project_id, decision=decision, notes=notes)
    return {
        "task": "resume_project",
        "project_id": project_id,
        "status": result.get("status"),
        "result": result,
    }
