from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from graphmovie.config import Settings, settings


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectStore:
    def save(self, project_id: str, payload: dict[str, Any]) -> None: ...
    def get(self, project_id: str) -> dict[str, Any] | None: ...
    def upsert_from_state(self, state: dict[str, Any]) -> dict[str, Any]: ...


class SqliteProjectStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS movie_projects (
                    project_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, project_id: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO movie_projects(project_id, status, payload, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    status=excluded.status,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (project_id, payload.get("status") or "unknown", body, _utcnow()),
            )
            conn.commit()

    def get(self, project_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM movie_projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["payload"])

    def upsert_from_state(self, state: dict[str, Any]) -> dict[str, Any]:
        request = state.get("request") or {}
        project_id = request.get("project_id")
        if not project_id:
            raise ValueError("state.request.project_id is required")
        payload = {
            "project_id": project_id,
            "request": request,
            "status": state.get("status"),
            "error": state.get("error"),
            "dispatch": state.get("dispatch") or [],
            "dispatch_log": state.get("dispatch_log") or [],
            "candidates": state.get("candidates") or [],
            "scores": state.get("scores") or {},
            "best_strategy": state.get("best_strategy"),
            "selected_plan": state.get("selected_plan"),
            "final_plan": state.get("final_plan"),
            "audits": state.get("audits") or [],
            "revision_round": state.get("revision_round") or 0,
            "revision_notes": state.get("revision_notes"),
            "review_decision": state.get("review_decision"),
            "updated_at": _utcnow(),
        }
        self.save(project_id, payload)
        return payload


def build_store(cfg: Settings | None = None) -> SqliteProjectStore:
    cfg = cfg or settings
    return SqliteProjectStore(cfg.runtime_dir / "projects.sqlite")
