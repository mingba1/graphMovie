from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from graphmovie.config import settings
from graphmovie.nodes.audit import audit_agent
from graphmovie.nodes.budget import budget_agent
from graphmovie.nodes.fail import fail_request
from graphmovie.nodes.finalize import finalize_agent
from graphmovie.nodes.intake import intake_agent
from graphmovie.nodes.research import (
    audio_agent,
    catalog_agent,
    cast_agent,
    footage_agent,
    join_research,
    location_agent,
)
from graphmovie.nodes.review import review_agent
from graphmovie.nodes.score import collect_routes, score_agent, select_best
from graphmovie.nodes.storyboard import storyboard_agent
from graphmovie.nodes.supervisor import (
    agents_from_notes,
    storyboard_sends,
    supervisor,
    supervisor_update,
)
from graphmovie.state import MovieState
from graphmovie.tracing import node_metadata


def _after_intake(state: MovieState) -> str:
    if state.get("status") == "failed" or state.get("error"):
        return "fail_request"
    return "prepare_dispatch"


def _after_prepare(state: MovieState) -> Any:
    return supervisor(state)


def _after_join(state: MovieState) -> Any:
    return storyboard_sends(state)


def _after_select(state: MovieState) -> str:
    if state.get("status") == "failed" or not state.get("best_strategy"):
        return "fail_request"
    return "review_agent"


def _after_review(state: MovieState) -> Any:
    if state.get("status") == "failed":
        return "fail_request"
    if state.get("review_decision") == "approve":
        return "finalize_agent"

    notes = state.get("revision_notes") or ""
    named = agents_from_notes(notes)
    request = state.get("request") or {}
    if "footage_agent" in named and request.get("footage_source") != "stock":
        named = [agent for agent in named if agent != "footage_agent"]
    if named:
        return "prepare_dispatch"
    return storyboard_sends(state)


def _after_collect(state: MovieState) -> str:
    return "score_agent"


def build_graph():
    graph = StateGraph(MovieState)

    graph.add_node("intake_agent", intake_agent, metadata=node_metadata("intake_agent"))
    graph.add_node(
        "prepare_dispatch",
        supervisor_update,
        metadata=node_metadata("supervisor"),
    )
    graph.add_node("catalog_agent", catalog_agent, metadata=node_metadata("catalog_agent"))
    graph.add_node("cast_agent", cast_agent, metadata=node_metadata("cast_agent"))
    graph.add_node("audio_agent", audio_agent, metadata=node_metadata("audio_agent"))
    graph.add_node(
        "location_agent", location_agent, metadata=node_metadata("location_agent")
    )
    graph.add_node("footage_agent", footage_agent, metadata=node_metadata("footage_agent"))
    graph.add_node(
        "join_research",
        join_research,
        defer=True,
        metadata=node_metadata("join_research"),
    )
    graph.add_node(
        "storyboard_agent",
        storyboard_agent,
        metadata=node_metadata("storyboard_agent"),
    )
    graph.add_node("budget_agent", budget_agent, metadata=node_metadata("budget_agent"))
    graph.add_node("audit_agent", audit_agent, metadata=node_metadata("audit_agent"))
    graph.add_node(
        "collect_routes",
        collect_routes,
        defer=True,
        metadata=node_metadata("collect_routes"),
    )
    graph.add_node("score_agent", score_agent, metadata=node_metadata("score_agent"))
    graph.add_node("select_best", select_best, metadata=node_metadata("select_best"))
    graph.add_node("review_agent", review_agent, metadata=node_metadata("review_agent"))
    graph.add_node(
        "finalize_agent", finalize_agent, metadata=node_metadata("finalize_agent")
    )
    graph.add_node("fail_request", fail_request, metadata=node_metadata("fail_request"))

    graph.add_edge(START, "intake_agent")
    graph.add_conditional_edges(
        "intake_agent",
        _after_intake,
        ["prepare_dispatch", "fail_request"],
    )
    graph.add_conditional_edges("prepare_dispatch", _after_prepare)
    graph.add_conditional_edges("join_research", _after_join)
    graph.add_edge("collect_routes", "score_agent")
    graph.add_edge("score_agent", "select_best")
    graph.add_conditional_edges(
        "select_best",
        _after_select,
        ["review_agent", "fail_request"],
    )
    graph.add_conditional_edges("review_agent", _after_review)
    graph.add_edge("finalize_agent", END)
    graph.add_edge("fail_request", END)
    return graph


def compile_graph(checkpointer: Any | None = None):
    graph = build_graph()
    if checkpointer is None:
        checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


def build_checkpointer(database_url: str | None = None):
    database_url = database_url if database_url is not None else settings.database_url
    if not database_url:
        return MemorySaver()
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Postgres support requires graphmovie[postgres] extras"
        ) from exc

    saver = PostgresSaver.from_conn_string(database_url)
    # from_conn_string is a context manager in some versions; normalize.
    if hasattr(saver, "__enter__"):
        # Keep a long-lived connection by entering once for process lifetime.
        # Callers that need cleanup should hold the context themselves.
        return _PostgresHolder(database_url)
    return saver


class _PostgresHolder:
    """Own a PostgresSaver connection for the process lifetime."""

    def __init__(self, conn_string: str) -> None:
        from langgraph.checkpoint.postgres import PostgresSaver

        self._cm = PostgresSaver.from_conn_string(conn_string)
        self.saver = self._cm.__enter__()
        self.saver.setup()

    def __getattr__(self, name: str):
        return getattr(self.saver, name)

    def close(self) -> None:
        self._cm.__exit__(None, None, None)


@lru_cache(maxsize=1)
def get_compiled_graph():
    checkpointer = build_checkpointer()
    return compile_graph(checkpointer=checkpointer)
