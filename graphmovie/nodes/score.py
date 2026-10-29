from __future__ import annotations

from typing import Any

from graphmovie.scoring import pick_best, score_plan
from graphmovie.state import MovieState


def collect_routes(state: MovieState) -> dict[str, Any]:
    return {"status": "candidates_ready"}


def score_agent(state: MovieState) -> dict[str, Any]:
    request = state["request"]
    scores: dict[str, dict[str, Any]] = {}
    # Keep the latest candidate per strategy.
    latest: dict[str, dict[str, Any]] = {}
    for plan in state.get("candidates") or []:
        latest[plan["strategy"]] = plan
    for strategy, plan in latest.items():
        scores[strategy] = score_plan(plan, request).model_dump()
    # Also mark discarded strategies seen in audits with no candidate.
    for audit in state.get("audits") or []:
        strategy = audit["strategy"]
        if strategy not in scores and audit.get("decision") == "discard":
            scores[strategy] = score_plan(
                {
                    "strategy": strategy,
                    "shots": [],
                    "total_cost_cny": request["budget_cny"] + 1,
                    "total_duration_sec": 0,
                },
                request,
            ).model_dump()
    return {"scores": scores, "status": "scored"}


def select_best(state: MovieState) -> dict[str, Any]:
    scores = state.get("scores") or {}
    best = pick_best(scores)
    if not best:
        return {
            "best_strategy": None,
            "selected_plan": None,
            "status": "failed",
            "error": "no_viable_plan",
        }
    latest = {plan["strategy"]: plan for plan in state.get("candidates") or []}
    return {
        "best_strategy": best,
        "selected_plan": latest.get(best),
        "status": "awaiting_review",
    }
