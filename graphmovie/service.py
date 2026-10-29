from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphInterrupt
from langgraph.types import Command

from graphmovie.config import Settings, settings
from graphmovie.export import to_json, to_markdown
from graphmovie.graph import compile_graph
from graphmovie.state import MovieRequest
from graphmovie.store import ProjectStore, SqliteProjectStore, build_store
from graphmovie.tracing import run_config


def _interrupt_payload(result: dict[str, Any] | Any) -> Any | None:
    interrupts = getattr(result, "interrupts", None)
    if interrupts:
        first = interrupts[0]
        return getattr(first, "value", first)
    if isinstance(result, dict):
        raw = result.get("__interrupt__")
        if raw:
            first = raw[0]
            return getattr(first, "value", first)
    return None


def _interrupt_from_exc(exc: GraphInterrupt) -> Any:
    args = exc.args[0] if exc.args else None
    if isinstance(args, (list, tuple)) and args:
        first = args[0]
        return getattr(first, "value", first)
    return getattr(args, "value", args)


class MovieService:
    def __init__(
        self,
        *,
        checkpointer: Any | None = None,
        store: ProjectStore | None = None,
        cfg: Settings | None = None,
    ) -> None:
        self.cfg = cfg or settings
        self.store = store or build_store(self.cfg)
        self.checkpointer = checkpointer or MemorySaver()
        self.graph = compile_graph(checkpointer=self.checkpointer)

    def create(self, request: MovieRequest | dict[str, Any]) -> dict[str, Any]:
        model = (
            request
            if isinstance(request, MovieRequest)
            else MovieRequest.model_validate(request)
        )
        config = run_config(model.project_id)
        try:
            result = self.graph.invoke(
                {
                    "request": model.model_dump(),
                    "revision_round": 0,
                    "dispatch_log": [],
                    "drafts": [],
                    "priced_routes": [],
                    "audits": [],
                    "candidates": [],
                    "footage": [],
                },
                config=config,
            )
        except GraphInterrupt as exc:
            return self._persist_interrupt(model.project_id, _interrupt_from_exc(exc))
        return self._persist_result(result, model.project_id)

    def resume(
        self,
        project_id: str,
        *,
        decision: str = "approve",
        notes: str | None = None,
    ) -> dict[str, Any]:
        config = run_config(project_id)
        payload: dict[str, Any] = {"decision": decision}
        if notes:
            payload["notes"] = notes
        try:
            result = self.graph.invoke(Command(resume=payload), config=config)
        except GraphInterrupt as exc:
            return self._persist_interrupt(project_id, _interrupt_from_exc(exc))
        return self._persist_result(result, project_id)

    def get(self, project_id: str) -> dict[str, Any] | None:
        saved = self.store.get(project_id)
        if saved:
            return saved
        config = run_config(project_id)
        snap = self.graph.get_state(config)
        if not snap or not snap.values:
            return None
        return self.store.upsert_from_state(dict(snap.values))

    def export(self, project_id: str, fmt: str = "markdown") -> str:
        project = self.get(project_id)
        if not project:
            raise KeyError(project_id)
        if fmt == "json":
            return to_json(project)
        return to_markdown(project)

    def _persist_interrupt(self, project_id: str, interrupt: Any) -> dict[str, Any]:
        config = run_config(project_id)
        snap = self.graph.get_state(config)
        values = dict(snap.values or {})
        values.setdefault("request", {"project_id": project_id})
        values["status"] = "interrupted"
        payload = self.store.upsert_from_state(values)
        payload["interrupt"] = interrupt
        return payload

    def _persist_result(self, result: Any, project_id: str) -> dict[str, Any]:
        interrupt = _interrupt_payload(result)
        if interrupt is not None:
            return self._persist_interrupt(project_id, interrupt)

        if hasattr(result, "values") and isinstance(result.values, dict):
            values = dict(result.values)
        elif isinstance(result, dict):
            values = dict(result)
        else:
            values = {"request": {"project_id": project_id}, "status": "unknown"}
        # Newer LangGraph may return state without raising while tasks still pending.
        config = run_config(project_id)
        snap = self.graph.get_state(config)
        if snap and snap.next:
            values = dict(snap.values or values)
            values["status"] = "interrupted"
            payload = self.store.upsert_from_state(values)
            tasks = list(snap.tasks or [])
            if tasks and getattr(tasks[0], "interrupts", None):
                payload["interrupt"] = tasks[0].interrupts[0].value
            return payload
        return self.store.upsert_from_state(values)


def build_service(cfg: Settings | None = None) -> MovieService:
    cfg = cfg or settings
    checkpointer: Any
    if cfg.database_url:
        from graphmovie.graph import build_checkpointer

        checkpointer = build_checkpointer(cfg.database_url)
    else:
        checkpointer = MemorySaver()
    store: SqliteProjectStore = build_store(cfg)
    return MovieService(checkpointer=checkpointer, store=store, cfg=cfg)
