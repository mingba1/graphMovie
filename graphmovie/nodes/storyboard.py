from __future__ import annotations

from langgraph.types import Command, Send

from graphmovie.llm import get_planner
from graphmovie.state import MovieState


def storyboard_agent(state: MovieState) -> Command:
    request = dict(state["request"])
    request["_revision_round"] = int(state.get("revision_round") or 0)
    strategy = state["strategy"]
    attempt = int(state.get("attempt") or 1)
    planner = get_planner()
    draft = planner(
        request=request,
        strategy=strategy,
        catalog=state.get("catalog") or [],
        cast=state.get("cast") or [],
        audio=state.get("audio") or [],
        locations=state.get("locations") or [],
        footage=state.get("footage") or [],
        revision_notes=state.get("revision_notes"),
        attempt=attempt,
    )
    payload = draft.model_dump()
    return Command(
        update={"drafts": [payload]},
        goto=Send(
            "budget_agent",
            {
                **state,
                "strategy": strategy,
                "attempt": attempt,
                "draft": payload,
            },
        ),
    )
