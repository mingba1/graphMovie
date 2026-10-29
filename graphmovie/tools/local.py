from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from graphmovie.config import Settings, settings


def _load_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list")
    return data


def _score_item(item: dict[str, Any], needles: set[str]) -> int:
    haystack = set(item.get("tags", [])) | set(item.get("styles", []))
    haystack.add(str(item.get("name", "")))
    return len(needles & haystack)


class _CachedJsonTool:
    def __init__(self, path: Path, source: str) -> None:
        self._path = path
        self._source = source
        self._lock = threading.Lock()
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._rows = _load_json(path)

    def _cached(self, key: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self._lock:
            hit = key in self._cache
            if not hit:
                self._cache[key] = rows
            payload = self._cache[key]
        return [
            {
                **row,
                "quote_id": f"{self._source}:{row['id']}",
                "source": self._source,
                "cache_hit": hit,
            }
            for row in payload
        ]


class LocalCatalogTool(_CachedJsonTool):
    def search(self, *, style: str, genre: str, tags: list[str] | None = None) -> list[dict[str, Any]]:
        tags = tags or []
        key = f"catalog:{style}:{genre}:{','.join(sorted(tags))}"
        needles = {style, genre, *tags}
        ranked = sorted(
            self._rows,
            key=lambda row: (
                0 if style in row.get("styles", []) else 1,
                -_score_item(row, needles),
                row["id"],
            ),
        )
        return self._cached(key, ranked)


class LocalCastTool(_CachedJsonTool):
    def search(self, *, genre: str, style: str) -> list[dict[str, Any]]:
        key = f"cast:{genre}:{style}"
        needles = {genre, style}
        ranked = sorted(self._rows, key=lambda row: (-_score_item(row, needles), row["id"]))
        return self._cached(key, ranked)


class LocalAudioTool(_CachedJsonTool):
    def search(self, *, style: str, tags: list[str] | None = None) -> list[dict[str, Any]]:
        tags = tags or []
        key = f"audio:{style}:{','.join(sorted(tags))}"
        needles = {style, *tags}
        ranked = sorted(self._rows, key=lambda row: (-_score_item(row, needles), row["id"]))
        return self._cached(key, ranked)


class LocalLocationTool(_CachedJsonTool):
    def search(self, *, style: str, genre: str) -> list[dict[str, Any]]:
        key = f"location:{style}:{genre}"
        needles = {style, genre}
        ranked = sorted(self._rows, key=lambda row: (-_score_item(row, needles), row["id"]))
        return self._cached(key, ranked)


class LocalFootageTool(_CachedJsonTool):
    def search(self, *, tags: list[str] | None = None) -> list[dict[str, Any]]:
        tags = tags or []
        key = f"footage:{','.join(sorted(tags))}"
        needles = set(tags)
        ranked = sorted(self._rows, key=lambda row: (-_score_item(row, needles), row["id"]))
        return self._cached(key, ranked)


class LocalToolBundle:
    def __init__(self, data_dir: Path) -> None:
        self.catalog = LocalCatalogTool(data_dir / "catalog.json", "catalog")
        self.cast = LocalCastTool(data_dir / "cast.json", "cast")
        self.audio = LocalAudioTool(data_dir / "audio.json", "audio")
        self.location = LocalLocationTool(data_dir / "locations.json", "location")
        self.footage = LocalFootageTool(data_dir / "footage.json", "footage")


def build_tools(cfg: Settings | None = None) -> LocalToolBundle:
    cfg = cfg or settings
    if cfg.tool_backend != "local":
        raise ValueError(f"Unsupported TOOL_BACKEND={cfg.tool_backend}")
    return LocalToolBundle(cfg.data_dir)
