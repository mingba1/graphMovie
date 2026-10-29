from __future__ import annotations

from graphmovie.config import settings

try:
    from celery import Celery
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Celery is required for async jobs. Install with: uv sync --extra worker"
    ) from exc

_eager = settings.celery_task_always_eager
_broker = "memory://" if _eager else settings.celery_broker_url
_backend = "cache+memory://" if _eager else settings.celery_result_backend

celery_app = Celery(
    "graphmovie",
    broker=_broker,
    backend=_backend,
    include=["graphmovie.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=_eager,
    task_eager_propagates=True,
    task_store_eager_result=True,
    task_soft_time_limit=settings.celery_soft_time_limit_sec,
    task_time_limit=settings.celery_time_limit_sec,
    result_expires=86400,
    cache_backend="memory",
    task_routes={
        "graphmovie.tasks.plan_project": {"queue": "graphmovie"},
        "graphmovie.tasks.resume_project": {"queue": "graphmovie"},
    },
)


def enable_eager_mode() -> None:
    """Force in-process execution for tests without Redis."""
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    celery_app.conf.task_store_eager_result = True
    celery_app.conf.broker_url = "memory://"
    celery_app.conf.result_backend = "cache+memory://"
    celery_app.conf.cache_backend = "memory"
