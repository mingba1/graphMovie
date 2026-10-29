from __future__ import annotations

from langgraph.types import Command, Send

from graphmovie.config import settings
from graphmovie.state import AuditReport, MovieState, PriceError


def audit_agent(state: MovieState) -> Command:
    priced = state["priced"]
    attempt = int(state.get("attempt") or priced.get("attempt") or 1)
    catalog_ids = {row["id"] for row in state.get("catalog") or []}
    location_ids = {row["id"] for row in state.get("locations") or []}
    footage_ids = {row["id"] for row in state.get("footage") or []}
    known_shot_ids = catalog_ids | footage_ids

    hallucinations: list[str] = []
    price_errors: list[PriceError] = []

    catalog_prices = {
        row["id"]: int(row["base_cost_cny"]) for row in state.get("catalog") or []
    }

    for shot in priced.get("shots") or []:
        shot_id = shot["shot_id"]
        name = shot.get("name") or shot_id
        if shot_id not in known_shot_ids:
            hallucinations.append(name)
            continue
        expected = catalog_prices.get(shot_id)
        actual = shot.get("catalog_price")
        if expected is not None and actual is not None and int(actual) != int(expected):
            price_errors.append(
                PriceError(
                    shot_id=shot_id,
                    name=name,
                    expected=int(expected),
                    actual=int(actual),
                    delta=int(actual) - int(expected),
                )
            )
        location_id = shot.get("location_id")
        if location_id and location_id not in location_ids:
            hallucinations.append(f"scene:{location_id}")

    if hallucinations or price_errors:
        if attempt < settings.max_route_retries:
            decision = "retry"
        else:
            decision = "discard"
    else:
        decision = "accept"

    report = AuditReport(
        strategy=priced["strategy"],
        attempt=attempt,
        hallucinations=hallucinations,
        price_errors=price_errors,
        decision=decision,
        agent_blame={
            "storyboard_agent": hallucinations,
            "budget_agent": [f"{err.shot_id}:{err.delta}" for err in price_errors],
        },
    )
    update = {"audits": [report.model_dump()]}

    if decision == "accept":
        update["candidates"] = [priced]
        return Command(update=update, goto="collect_routes")

    if decision == "retry":
        notes = state.get("revision_notes") or ""
        retry_notes = notes
        if hallucinations:
            retry_notes = f"{retry_notes};avoid:{','.join(hallucinations)}".strip(";")
        return Command(
            update=update,
            goto=Send(
                "storyboard_agent",
                {
                    **state,
                    "strategy": priced["strategy"],
                    "attempt": attempt + 1,
                    "revision_notes": retry_notes or state.get("revision_notes"),
                },
            ),
        )

    return Command(update=update, goto="collect_routes")
