from __future__ import annotations

import os
from typing import Any


def tracing_enabled() -> bool:
    return os.getenv("LANGSMITH_TRACING", "").lower() in {"1", "true", "yes"}


def run_config(project_id: str, **extra: Any) -> dict[str, Any]:
    configurable = {"thread_id": project_id}
    metadata = {"project_id": project_id, **extra}
    config: dict[str, Any] = {
        "configurable": configurable,
        "metadata": metadata,
        "tags": ["graphmovie", f"project:{project_id}"],
    }
    if tracing_enabled():
        config["run_name"] = f"graphmovie:{project_id}"
    return config


def node_metadata(agent: str) -> dict[str, str]:
    return {"agent": agent}
