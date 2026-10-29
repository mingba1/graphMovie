from __future__ import annotations

from typing import Any

from graphmovie.state import MovieState


def fail_request(state: MovieState) -> dict[str, Any]:
    return {
        "status": "failed",
        "error": state.get("error") or "failed",
        "final_plan": None,
    }
