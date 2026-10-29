from __future__ import annotations

from typing import Any

from graphmovie.config import PACE_TARGET_SECONDS, Settings, settings
from graphmovie.state import RouteDraft, Shot


STRATEGY_PROFILES: dict[str, dict[str, Any]] = {
    "fast_social": {
        "title_suffix": "短视频快节奏版",
        "duration_factor": 0.85,
        "prefer_tags": {"fast", "packed", "montage", "action", "fast_social"},
        "max_shot_sec": 4.0,
        "cost_bias": "low",
    },
    "balanced": {
        "title_suffix": "均衡叙事版",
        "duration_factor": 1.0,
        "prefer_tags": {"balanced", "dialogue", "character", "urban"},
        "max_shot_sec": 7.0,
        "cost_bias": "mid",
    },
    "cinematic": {
        "title_suffix": "电影感长镜头版",
        "duration_factor": 1.05,
        "prefer_tags": {"cinematic", "wide", "drama", "ending", "detail"},
        "max_shot_sec": 10.0,
        "cost_bias": "high",
    },
}


def _filter_catalog(catalog: list[dict[str, Any]], style: str) -> list[dict[str, Any]]:
    preferred = [row for row in catalog if style in row.get("styles", [])]
    return preferred or list(catalog)


def _shot_score(row: dict[str, Any], prefer_tags: set[str], cost_bias: str) -> tuple:
    tags = set(row.get("tags") or [])
    overlap = len(tags & prefer_tags)
    cost = int(row.get("base_cost_cny") or 0)
    if cost_bias == "low":
        return (-overlap, cost, row["id"])
    if cost_bias == "high":
        return (-overlap, -cost, row["id"])
    return (-overlap, abs(cost - 350), row["id"])


def _pick_location(locations: list[dict[str, Any]], tags: set[str]) -> str | None:
    if not locations:
        return None
    ranked = sorted(
        locations,
        key=lambda row: (-len(set(row.get("tags") or []) & tags), row["id"]),
    )
    return ranked[0]["id"]


def _pick_cast(cast: list[dict[str, Any]], style: str, genre: str) -> list[str]:
    if not cast:
        return []
    ranked = sorted(
        cast,
        key=lambda row: (
            -len(set(row.get("tags") or []) & {style, genre, "lead"}),
            row["id"],
        ),
    )
    return [ranked[0]["id"]] + ([ranked[1]["id"]] if len(ranked) > 1 else [])


def _pick_audio(audio: list[dict[str, Any]], tags: set[str], style: str) -> list[str]:
    if not audio:
        return []
    ranked = sorted(
        audio,
        key=lambda row: (-len(set(row.get("tags") or []) & ({style, *tags})), row["id"]),
    )
    return [ranked[0]["id"]]


def _pick_footage(footage: list[dict[str, Any]], tags: set[str]) -> str | None:
    if not footage:
        return None
    ranked = sorted(
        footage,
        key=lambda row: (-len(set(row.get("tags") or []) & tags), row["id"]),
    )
    return ranked[0]["id"]


def build_storyboard(
    *,
    request: dict[str, Any],
    strategy: str,
    catalog: list[dict[str, Any]],
    cast: list[dict[str, Any]],
    audio: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    footage: list[dict[str, Any]],
    revision_notes: str | None = None,
    attempt: int = 1,
    inject_hallucination: bool = False,
) -> RouteDraft:
    profile = STRATEGY_PROFILES[strategy]
    style = request["style"]
    genre = request["genre"]
    pace = request.get("pace", "balanced")
    target = int(request["duration_sec"]) * float(profile["duration_factor"])
    if revision_notes and ("短" in revision_notes or "快" in revision_notes):
        target *= 0.9
        profile = {**profile, "max_shot_sec": min(float(profile["max_shot_sec"]), 4.0)}

    rows = sorted(
        _filter_catalog(catalog, style),
        key=lambda row: _shot_score(row, set(profile["prefer_tags"]), profile["cost_bias"]),
    )
    if not rows:
        raise ValueError("catalog is empty")

    lead_cast = _pick_cast(cast, style, genre)
    shots: list[Shot] = []
    total = 0.0
    idx = 0
    pace_target = PACE_TARGET_SECONDS.get(pace, 5.0)

    # Always open with title card when available.
    title_rows = [row for row in rows if "title" in set(row.get("tags") or [])]
    ordered = title_rows + [row for row in rows if row not in title_rows]

    while total < target and len(shots) < 24:
        row = ordered[idx % len(ordered)]
        idx += 1
        tags = set(row.get("tags") or [])
        duration = min(float(row["base_duration_sec"]), float(profile["max_shot_sec"]))
        if strategy == "balanced":
            duration = min(max(duration, pace_target - 1), float(profile["max_shot_sec"]))
        if strategy == "cinematic":
            duration = max(duration, min(float(row["base_duration_sec"]), float(profile["max_shot_sec"])))
        if strategy == "fast_social":
            duration = min(duration, 3.5)

        shot = Shot(
            shot_id=row["id"],
            name=row["name"],
            duration_sec=round(duration, 2),
            tags=list(row.get("tags") or []),
            location_id=_pick_location(locations, tags),
            cast_ids=lead_cast[:1] if "dialogue" in tags or "character" in tags else lead_cast[:1],
            audio_ids=_pick_audio(audio, tags, style),
            footage_id=(
                _pick_footage(footage, tags)
                if request.get("footage_source") == "stock"
                else None
            ),
            narration=f"{request['title']} · {row['name']}",
        )
        shots.append(shot)
        total += duration
        if total >= target:
            break

    if inject_hallucination:
        shots.append(
            Shot(
                shot_id="shot_moon_opera",
                name="不存在的月球歌剧院",
                duration_sec=5.0,
                tags=["hallucination"],
                narration="审计应标为幻觉",
            )
        )
        total += 5.0

    highlights = [
        f"策略={strategy}",
        f"风格={style}",
        f"镜头数={len(shots)}",
    ]
    if revision_notes:
        highlights.append(f"修订={revision_notes[:40]}")

    return RouteDraft(
        strategy=strategy,
        title=f"{request['title']} · {profile['title_suffix']}",
        shots=shots,
        total_duration_sec=round(total, 2),
        highlights=highlights,
        attempt=attempt,
        revision_round=int(request.get("_revision_round") or 0),
    )


def get_planner(cfg: Settings | None = None):
    """Return the active storyboard planner.

    LLM mode is reserved for the same RouteDraft contract. Until a model is
    configured, the offline planner remains the production default.
    """
    cfg = cfg or settings
    if cfg.use_llm:
        # Keep a single call site even when LLM extras are not installed.
        return build_storyboard
    return build_storyboard
