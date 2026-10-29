from __future__ import annotations

import operator
import uuid
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field, field_validator

from graphmovie.config import FOOTAGE_SOURCES, PACES, STYLES


class MovieRequest(BaseModel):
    title: str
    genre: str
    style: Literal["cinematic", "anime", "documentary"]
    duration_sec: int = Field(ge=15, le=600)
    budget_cny: int = Field(ge=500)
    pace: Literal["relaxed", "balanced", "packed"] = "balanced"
    footage_source: Literal["generated", "stock"] = "generated"
    delivery_date: str | None = None
    interests: list[str] = Field(default_factory=list)
    project_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    @field_validator("style")
    @classmethod
    def _style(cls, value: str) -> str:
        if value not in STYLES:
            raise ValueError(f"style must be one of {STYLES}")
        return value

    @field_validator("pace")
    @classmethod
    def _pace(cls, value: str) -> str:
        if value not in PACES:
            raise ValueError(f"pace must be one of {PACES}")
        return value

    @field_validator("footage_source")
    @classmethod
    def _footage(cls, value: str) -> str:
        if value not in FOOTAGE_SOURCES:
            raise ValueError(f"footage_source must be one of {FOOTAGE_SOURCES}")
        return value

    @field_validator("title", "genre")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned


class Shot(BaseModel):
    shot_id: str
    name: str
    duration_sec: float
    tags: list[str] = Field(default_factory=list)
    location_id: str | None = None
    cast_ids: list[str] = Field(default_factory=list)
    audio_ids: list[str] = Field(default_factory=list)
    footage_id: str | None = None
    narration: str = ""
    cost_cny: int | None = None
    catalog_price: int | None = None


class RouteDraft(BaseModel):
    strategy: str
    title: str
    shots: list[Shot]
    total_duration_sec: float
    highlights: list[str] = Field(default_factory=list)
    attempt: int = 1
    revision_round: int = 0


class RoutePlan(RouteDraft):
    total_cost_cny: int
    quote_ids: list[str] = Field(default_factory=list)


class PriceError(BaseModel):
    shot_id: str
    name: str
    expected: int
    actual: int
    delta: int


class AuditReport(BaseModel):
    strategy: str
    attempt: int
    hallucinations: list[str] = Field(default_factory=list)
    price_errors: list[PriceError] = Field(default_factory=list)
    decision: Literal["accept", "retry", "discard"]
    agent_blame: dict[str, list[str]] = Field(default_factory=dict)


class ScoreBreakdown(BaseModel):
    cost: float
    time: float
    style_fit: float
    pace_fit: float
    total: float
    rejected_reason: str | None = None


class MovieState(TypedDict, total=False):
    request: dict[str, Any]
    dispatch: list[str]
    dispatch_log: Annotated[list[str], operator.add]
    catalog: list[dict[str, Any]]
    cast: list[dict[str, Any]]
    audio: list[dict[str, Any]]
    locations: list[dict[str, Any]]
    footage: list[dict[str, Any]]
    drafts: Annotated[list[dict[str, Any]], operator.add]
    priced_routes: Annotated[list[dict[str, Any]], operator.add]
    audits: Annotated[list[dict[str, Any]], operator.add]
    candidates: Annotated[list[dict[str, Any]], operator.add]
    scores: dict[str, dict[str, Any]]
    best_strategy: str | None
    selected_plan: dict[str, Any] | None
    revision_round: int
    revision_notes: str | None
    review_decision: str | None
    final_plan: dict[str, Any] | None
    error: str | None
    status: str
    # Per-task fields injected by Send payloads
    strategy: str
    attempt: int
    draft: dict[str, Any]
    priced: dict[str, Any]
