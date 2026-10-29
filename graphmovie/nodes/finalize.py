from __future__ import annotations

from typing import Any

from graphmovie.state import MovieState


def finalize_agent(state: MovieState) -> dict[str, Any]:
    plan = state.get("selected_plan") or state.get("final_plan")
    if not plan:
        return {
            "status": "failed",
            "error": "missing_selected_plan",
        }
    return {
        "final_plan": plan,
        "status": "approved",
        "error": None,
    }
