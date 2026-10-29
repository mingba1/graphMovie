from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from graphmovie.state import MovieRequest, MovieState


def intake_agent(state: MovieState) -> dict[str, Any]:
    raw = state.get("request") or {}
    try:
        request = MovieRequest.model_validate(raw)
    except ValidationError as exc:
        return {
            "status": "failed",
            "error": f"invalid_request: {exc.errors()[0]['msg']}",
        }
    return {
        "request": request.model_dump(),
        "status": "intake_ok",
        "revision_round": int(state.get("revision_round") or 0),
        "error": None,
    }
