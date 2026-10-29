from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / "data"

STRATEGIES = ("fast_social", "balanced", "cinematic")
STRATEGY_TIEBREAK = ("balanced", "fast_social", "cinematic")

STYLES = ("cinematic", "anime", "documentary")
PACES = ("relaxed", "balanced", "packed")
FOOTAGE_SOURCES = ("generated", "stock")

PACE_TARGET_SECONDS = {"relaxed": 8.0, "balanced": 5.0, "packed": 3.0}

RESEARCH_AGENTS = (
    "catalog_agent",
    "cast_agent",
    "audio_agent",
    "location_agent",
    "footage_agent",
)

ALWAYS_RESEARCH = (
    "catalog_agent",
    "cast_agent",
    "audio_agent",
    "location_agent",
)

RESEARCH_KEYWORDS: dict[str, tuple[str, ...]] = {
    "catalog_agent": ("素材库", "风格", "目录", "镜头库"),
    "cast_agent": ("角色", "配音", "演员", "更换角色"),
    "audio_agent": ("配乐", "音效", "音乐"),
    "location_agent": ("场景", "置景"),
    "footage_agent": ("库存", "航拍", "素材片", "stock"),
}


@dataclass(frozen=True)
class Settings:
    database_url: str | None = None
    tool_backend: str = "local"
    data_dir: Path = DEFAULT_DATA_DIR
    runtime_dir: Path = DEFAULT_DATA_DIR / "runtime"
    score_weights: dict[str, float] = field(
        default_factory=lambda: {
            "cost": 0.35,
            "time": 0.20,
            "style_fit": 0.30,
            "pace_fit": 0.15,
        }
    )
    max_revision_round: int = 3
    max_route_retries: int = 2
    use_llm: bool = False
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_task_always_eager: bool = False

    @classmethod
    def load(cls) -> Settings:
        data_dir = Path(
            os.getenv("GRAPHMOVIE_DATA_DIR")
            or os.getenv("GOMOVIE_DATA_DIR")
            or DEFAULT_DATA_DIR
        )
        use_llm = (
            os.getenv("GRAPHMOVIE_USE_LLM")
            or os.getenv("GOMOVIE_USE_LLM")
            or "0"
        ) == "1"
        eager = (
            os.getenv("CELERY_TASK_ALWAYS_EAGER")
            or os.getenv("GRAPHMOVIE_CELERY_EAGER")
            or "0"
        ).lower() in {"1", "true", "yes"}
        broker = os.getenv("CELERY_BROKER_URL") or "redis://localhost:6379/0"
        backend = os.getenv("CELERY_RESULT_BACKEND") or "redis://localhost:6379/1"
        return cls(
            database_url=os.getenv("DATABASE_URL") or None,
            tool_backend=os.getenv("TOOL_BACKEND", "local"),
            data_dir=data_dir,
            runtime_dir=data_dir / "runtime",
            use_llm=use_llm,
            celery_broker_url=broker,
            celery_result_backend=backend,
            celery_task_always_eager=eager,
        )


settings = Settings.load()
