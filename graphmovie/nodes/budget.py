from __future__ import annotations

from typing import Any

from langgraph.types import Command, Send

from graphmovie.state import MovieState, RoutePlan, Shot


def _index_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in rows}


def budget_agent(state: MovieState) -> Command:
    draft = state["draft"]
    catalog = _index_by_id(state.get("catalog") or [])
    cast = _index_by_id(state.get("cast") or [])
    audio = _index_by_id(state.get("audio") or [])
    locations = _index_by_id(state.get("locations") or [])
    footage = _index_by_id(state.get("footage") or [])

    priced_shots: list[Shot] = []
    quote_ids: list[str] = []
    total_cost = 0

    for raw in draft.get("shots") or []:
        shot = Shot.model_validate(raw)
        catalog_row = catalog.get(shot.shot_id)
        catalog_price = int(catalog_row["base_cost_cny"]) if catalog_row else None

        cost = catalog_price or 0
        if shot.location_id and shot.location_id in locations:
            loc = locations[shot.location_id]
            cost += int(loc.get("cost_cny") or 0)
            quote_ids.append(loc.get("quote_id") or f"location:{shot.location_id}")
        for cast_id in shot.cast_ids:
            if cast_id in cast:
                row = cast[cast_id]
                cost += int(row.get("cost_cny") or 0)
                quote_ids.append(row.get("quote_id") or f"cast:{cast_id}")
        for audio_id in shot.audio_ids:
            if audio_id in audio:
                row = audio[audio_id]
                cost += int(row.get("cost_cny") or 0)
                quote_ids.append(row.get("quote_id") or f"audio:{audio_id}")
        if shot.footage_id and shot.footage_id in footage:
            row = footage[shot.footage_id]
            cost += int(row.get("cost_cny") or 0)
            quote_ids.append(row.get("quote_id") or f"footage:{shot.footage_id}")
        if catalog_row:
            quote_ids.append(catalog_row.get("quote_id") or f"catalog:{shot.shot_id}")

        shot.cost_cny = cost
        shot.catalog_price = catalog_price
        priced_shots.append(shot)
        total_cost += cost

    plan = RoutePlan(
        strategy=draft["strategy"],
        title=draft["title"],
        shots=priced_shots,
        total_duration_sec=float(draft["total_duration_sec"]),
        highlights=list(draft.get("highlights") or []),
        attempt=int(draft.get("attempt") or state.get("attempt") or 1),
        revision_round=int(draft.get("revision_round") or 0),
        total_cost_cny=total_cost,
        quote_ids=sorted(set(quote_ids)),
    )
    payload = plan.model_dump()
    return Command(
        update={"priced_routes": [payload]},
        goto=Send(
            "audit_agent",
            {
                **state,
                "strategy": plan.strategy,
                "attempt": plan.attempt,
                "draft": draft,
                "priced": payload,
            },
        ),
    )
