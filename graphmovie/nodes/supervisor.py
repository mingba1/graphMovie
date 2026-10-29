from __future__ import annotations

from typing import Any

from langgraph.types import Send

from graphmovie.config import ALWAYS_RESEARCH, RESEARCH_KEYWORDS, STRATEGIES
from graphmovie.state import MovieState


def agents_from_notes(notes: str) -> list[str]:
    chosen: list[str] = []
    for agent, keywords in RESEARCH_KEYWORDS.items():
        if any(keyword in notes for keyword in keywords):
            chosen.append(agent)
    return chosen


def default_dispatch(request: dict[str, Any]) -> list[str]:
    agents = list(ALWAYS_RESEARCH)
    if request.get("footage_source") == "stock":
        agents.append("footage_agent")
    return agents


def storyboard_sends(state: MovieState) -> list[Send]:
    attempt = 1
    return [
        Send(
            "storyboard_agent",
            {
                **state,
                "strategy": strategy,
                "attempt": attempt,
            },
        )
        for strategy in STRATEGIES
    ]


def supervisor(state: MovieState) -> list[Send]:
    request = state.get("request") or {}
    notes = (state.get("revision_notes") or "").strip()
    revision_round = int(state.get("revision_round") or 0)

    if revision_round > 0 and notes:
        named = agents_from_notes(notes)
        if not named:
            return storyboard_sends(state)
        # Restrict footage agent to stock projects.
        if "footage_agent" in named and request.get("footage_source") != "stock":
            named = [agent for agent in named if agent != "footage_agent"]
        if not named:
            return storyboard_sends(state)
        return [
            Send(agent, {**state, "request": request})
            for agent in named
        ]

    agents = default_dispatch(request)
    return [Send(agent, {**state, "request": request}) for agent in agents]


def supervisor_update(state: MovieState) -> dict[str, Any]:
    """Record dispatch decisions before fan-out edges run.

    Used when the graph needs an explicit state write; the primary fan-out is
    handled by the conditional edge that calls `supervisor`.
    """
    request = state.get("request") or {}
    notes = (state.get("revision_notes") or "").strip()
    revision_round = int(state.get("revision_round") or 0)
    if revision_round > 0 and notes:
        agents = agents_from_notes(notes)
        if "footage_agent" in agents and request.get("footage_source") != "stock":
            agents = [agent for agent in agents if agent != "footage_agent"]
        if not agents:
            agents = []
    else:
        agents = default_dispatch(request)
    return {
        "dispatch": agents,
        "dispatch_log": agents,
        "status": "researching" if agents else "routing",
    }
