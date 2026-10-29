from __future__ import annotations

from graphmovie.config import settings


class SharedCheckpointerRequired(RuntimeError):
    """Raised when multi-process resume cannot share graph checkpoints."""


def require_shared_checkpointer(*, operation: str) -> None:
    """Fail fast when Celery workers cannot share LangGraph checkpoints.

    MemorySaver is process-local. Cross-process resume needs DATABASE_URL /
    PostgresSaver, unless tasks run in-process (eager mode).
    """
    if settings.celery_task_always_eager:
        return
    if settings.database_url:
        return
    raise SharedCheckpointerRequired(
        f"{operation} requires DATABASE_URL (PostgresSaver) when Celery is not eager. "
        "API and worker processes cannot share MemorySaver checkpoints."
    )
