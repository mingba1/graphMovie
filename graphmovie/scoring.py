from __future__ import annotations

from typing import Any

from graphmovie.config import PACE_TARGET_SECONDS, STRATEGY_TIEBREAK, Settings, settings
from graphmovie.state import ScoreBreakdown


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_plan(
    plan: dict[str, Any],
    request: dict[str, Any],
    *,
    cfg: Settings | None = None,
) -> ScoreBreakdown:
    cfg = cfg or settings
    weights = cfg.score_weights
    budget = max(int(request["budget_cny"]), 1)
    target_duration = max(int(request["duration_sec"]), 1)
    style = request["style"]
    pace = request.get("pace", "balanced")
    total_cost = int(plan.get("total_cost_cny") or 0)
    total_duration = float(plan.get("total_duration_sec") or 0.0)
    shots = plan.get("shots") or []

    if total_cost > budget:
        return ScoreBreakdown(
            cost=0.0,
            time=0.0,
            style_fit=0.0,
            pace_fit=0.0,
            total=0.0,
            rejected_reason="over_budget",
        )

    cost = _clamp(1.0 - (total_cost / budget))
    duration_ratio = abs(total_duration - target_duration) / target_duration
    time_score = _clamp(1.0 - duration_ratio)

    tag_hits = 0
    for shot in shots:
        tags = set(shot.get("tags") or [])
        if style in tags or style in (shot.get("name") or ""):
            tag_hits += 1
        elif any(style in tag for tag in tags):
            tag_hits += 1
    style_fit = _clamp(tag_hits / max(len(shots), 1))

    avg_shot = total_duration / max(len(shots), 1)
    target_shot = PACE_TARGET_SECONDS.get(pace, 5.0)
    pace_fit = _clamp(1.0 - abs(avg_shot - target_shot) / target_shot)

    total = (
        weights["cost"] * cost
        + weights["time"] * time_score
        + weights["style_fit"] * style_fit
        + weights["pace_fit"] * pace_fit
    )
    return ScoreBreakdown(
        cost=round(cost, 4),
        time=round(time_score, 4),
        style_fit=round(style_fit, 4),
        pace_fit=round(pace_fit, 4),
        total=round(total, 4),
    )


def pick_best(scores: dict[str, dict[str, Any]]) -> str | None:
    alive = [
        (strategy, payload)
        for strategy, payload in scores.items()
        if not payload.get("rejected_reason")
    ]
    if not alive:
        return None

    def sort_key(item: tuple[str, dict[str, Any]]) -> tuple[float, int]:
        strategy, payload = item
        tie = STRATEGY_TIEBREAK.index(strategy) if strategy in STRATEGY_TIEBREAK else 99
        return (-float(payload.get("total") or 0.0), tie)

    return sorted(alive, key=sort_key)[0][0]
