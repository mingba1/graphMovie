from __future__ import annotations

from typing import Any

from langgraph.types import Command

from graphmovie.state import MovieState
from graphmovie.tools import build_tools

_TOOLS = build_tools()


def catalog_agent(state: MovieState) -> Command:
    request = state["request"]
    rows = _TOOLS.catalog.search(
        style=request["style"],
        genre=request["genre"],
        tags=request.get("interests") or [],
    )
    return Command(update={"catalog": rows}, goto="join_research")


def cast_agent(state: MovieState) -> Command:
    request = state["request"]
    rows = _TOOLS.cast.search(genre=request["genre"], style=request["style"])
    return Command(update={"cast": rows}, goto="join_research")


def audio_agent(state: MovieState) -> Command:
    request = state["request"]
    rows = _TOOLS.audio.search(style=request["style"], tags=request.get("interests") or [])
    return Command(update={"audio": rows}, goto="join_research")


def location_agent(state: MovieState) -> Command:
    request = state["request"]
    rows = _TOOLS.location.search(style=request["style"], genre=request["genre"])
    return Command(update={"locations": rows}, goto="join_research")


def footage_agent(state: MovieState) -> Command:
    request = state["request"]
    rows = _TOOLS.footage.search(tags=request.get("interests") or [request["genre"]])
    return Command(update={"footage": rows}, goto="join_research")


def join_research(state: MovieState) -> dict[str, Any]:
    return {"status": "research_ready"}
