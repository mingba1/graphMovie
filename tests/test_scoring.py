from graphmovie.scoring import pick_best, score_plan


def test_score_rejects_over_budget():
    plan = {
        "strategy": "cinematic",
        "shots": [{"name": "a", "tags": ["cinematic"], "duration_sec": 5}],
        "total_cost_cny": 9000,
        "total_duration_sec": 60,
    }
    request = {
        "budget_cny": 8000,
        "duration_sec": 60,
        "style": "cinematic",
        "pace": "balanced",
    }
    score = score_plan(plan, request)
    assert score.rejected_reason == "over_budget"
    assert score.total == 0


def test_pick_best_tiebreak_prefers_balanced():
    scores = {
        "fast_social": {"total": 0.8},
        "balanced": {"total": 0.8},
        "cinematic": {"total": 0.8},
    }
    assert pick_best(scores) == "balanced"
