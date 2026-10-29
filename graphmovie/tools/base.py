from __future__ import annotations

from typing import Any, Protocol


class CatalogTool(Protocol):
    def search(self, *, style: str, genre: str, tags: list[str] | None = None) -> list[dict[str, Any]]: ...


class CastTool(Protocol):
    def search(self, *, genre: str, style: str) -> list[dict[str, Any]]: ...


class AudioTool(Protocol):
    def search(self, *, style: str, tags: list[str] | None = None) -> list[dict[str, Any]]: ...


class LocationTool(Protocol):
    def search(self, *, style: str, genre: str) -> list[dict[str, Any]]: ...


class FootageTool(Protocol):
    def search(self, *, tags: list[str] | None = None) -> list[dict[str, Any]]: ...


class ToolBundle(Protocol):
    catalog: CatalogTool
    cast: CastTool
    audio: AudioTool
    location: LocationTool
    footage: FootageTool
