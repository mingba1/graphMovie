from __future__ import annotations

from typing import Any

from langgraph.types import Overwrite, interrupt

from graphmovie.config import settings
from graphmovie.state import MovieState


def review_agent(state: MovieState) -> dict[str, Any]:
    payload = {
        "project_id": state["request"]["project_id"],
        "best_strategy": state.get("best_strategy"),
        "selected_plan": state.get("selected_plan"),
        "scores": state.get("scores"),
        "candidates": state.get("candidates"),
        "revision_round": int(state.get("revision_round") or 0),
        "prompt": "approve or revise with notes",
    }
    decision = interrupt(payload)
    if isinstance(decision, str):
        decision = {"decision": decision}
    if not isinstance(decision, dict):
        decision = {"decision": "approve"}

    choice = str(decision.get("decision") or "approve").strip().lower()
    notes = str(decision.get("notes") or "").strip() or None

    if choice.startswith("revise"):
        if ":" in choice and not notes:
            notes = choice.split(":", 1)[1].strip() or None
        choice = "revise"

    if choice == "revise":
        nxt = int(state.get("revision_round") or 0) + 1
        if nxt > settings.max_revision_round:
            return {
                "review_decision": "revise",
                "revision_notes": notes,
                "revision_round": nxt,
                "status": "failed",
                "error": "revision_limit_exceeded",
            }
        return {
            "review_decision": "revise",
            "revision_notes": notes,
            "revision_round": nxt,
            "drafts": Overwrite([]),
            "priced_routes": Overwrite([]),
            "audits": Overwrite([]),
            "candidates": Overwrite([]),
            "scores": {},
            "best_strategy": None,
            "selected_plan": None,
            "status": "revising",
        }

    return {
        "review_decision": "approve",
        "revision_notes": notes,
        "status": "approved_pending",
    }
