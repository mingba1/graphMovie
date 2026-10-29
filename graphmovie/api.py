from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from graphmovie.config import settings
from graphmovie.jobs import (
    WorkerUnavailableError,
    enqueue_plan,
    enqueue_resume,
    get_job,
)
from graphmovie.runtime_guards import SharedCheckpointerRequired
from graphmovie.security import (
    ApiKeyMiddleware,
    RateLimitMiddleware,
    RequestTimeoutMiddleware,
)
from graphmovie.service import MovieService, build_service
from graphmovie.state import MovieRequest

app = FastAPI(
    title="graphmovie",
    version="0.1.0",
    description=(
        "AI movie production planning API. Returns storyboards, budgets, and "
        "review decisions — not rendered video files."
    ),
)
app.add_middleware(RequestTimeoutMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(ApiKeyMiddleware)

_service: MovieService | None = None


def get_service() -> MovieService:
    global _service
    if _service is None:
        _service = build_service()
    return _service


class ResumeBody(BaseModel):
    decision: Literal["approve", "revise"] = "approve"
    notes: str | None = None


class CreateBody(BaseModel):
    title: str
    genre: str
    style: Literal["cinematic", "anime", "documentary"] = "cinematic"
    duration_sec: int = Field(default=60, ge=15, le=600)
    budget_cny: int = Field(default=8000, ge=500)
    pace: Literal["relaxed", "balanced", "packed"] = "balanced"
    footage_source: Literal["generated", "stock"] = "generated"
    delivery_date: str | None = None
    interests: list[str] = Field(default_factory=list)
    project_id: str | None = None


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "auth_enabled": bool(settings.api_keys),
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "request_timeout_sec": settings.request_timeout_sec,
        "product": "storyboard_planning",
    }


@app.post("/projects")
def create_project(body: CreateBody) -> dict[str, Any]:
    """Synchronous planning. Prefer /jobs/plan for production API traffic."""
    payload = body.model_dump(exclude_none=True)
    request = MovieRequest.model_validate(payload)
    return get_service().create(request)


@app.get("/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    project = get_service().get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@app.post("/projects/{project_id}/resume")
def resume_project(project_id: str, body: ResumeBody) -> dict[str, Any]:
    service = get_service()
    if not service.get(project_id):
        raise HTTPException(status_code=404, detail="project not found")
    return service.resume(project_id, decision=body.decision, notes=body.notes)


@app.get("/projects/{project_id}/export")
def export_project(
    project_id: str,
    fmt: Literal["markdown", "json"] = Query(default="markdown", alias="format"),
):
    service = get_service()
    try:
        content = service.export(project_id, fmt=fmt)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc
    media = "application/json" if fmt == "json" else "text/markdown; charset=utf-8"
    return PlainTextResponse(content, media_type=media)


@app.post("/jobs/plan", status_code=202)
def enqueue_plan_job(body: CreateBody) -> dict[str, Any]:
    """Enqueue LangGraph planning on Celery."""
    payload = body.model_dump(exclude_none=True)
    request = MovieRequest.model_validate(payload)
    try:
        job = enqueue_plan(request.model_dump())
    except WorkerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SharedCheckpointerRequired as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    job["project_id"] = request.project_id
    return job


@app.post("/jobs/{project_id}/resume", status_code=202)
def enqueue_resume_job(project_id: str, body: ResumeBody) -> dict[str, Any]:
    if not get_service().get(project_id):
        raise HTTPException(status_code=404, detail="project not found")
    try:
        return enqueue_resume(
            project_id,
            decision=body.decision,
            notes=body.notes,
        )
    except WorkerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SharedCheckpointerRequired as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/jobs/{task_id}")
def job_status(task_id: str) -> dict[str, Any]:
    try:
        return get_job(task_id)
    except WorkerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
