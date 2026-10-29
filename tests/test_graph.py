from langgraph.checkpoint.memory import MemorySaver

from graphmovie.service import MovieService
from graphmovie.state import MovieRequest
from graphmovie.store import SqliteProjectStore


def _service(tmp_path) -> MovieService:
    store = SqliteProjectStore(tmp_path / "projects.sqlite")
    return MovieService(checkpointer=MemorySaver(), store=store)


def test_generated_skips_footage_agent(tmp_path):
    service = _service(tmp_path)
    project = service.create(
        MovieRequest(
            title="雨夜霓虹",
            genre="科幻",
            style="cinematic",
            duration_sec=45,
            budget_cny=25000,
            pace="balanced",
            footage_source="generated",
        )
    )
    assert project["status"] == "interrupted"
    assert "footage_agent" not in project["dispatch_log"]
    assert len(project["candidates"]) >= 1


def test_stock_includes_footage_agent(tmp_path):
    service = _service(tmp_path)
    project = service.create(
        MovieRequest(
            title="雨夜霓虹",
            genre="科幻",
            style="cinematic",
            duration_sec=45,
            budget_cny=25000,
            footage_source="stock",
        )
    )
    assert "footage_agent" in project["dispatch_log"]


def test_approve_resume_and_export(tmp_path):
    service = _service(tmp_path)
    created = service.create(
        MovieRequest(
            title="雨夜霓虹",
            genre="科幻",
            style="cinematic",
            duration_sec=45,
            budget_cny=25000,
        )
    )
    project_id = created["project_id"]
    approved = service.resume(project_id, decision="approve")
    assert approved["status"] == "approved"
    assert approved["final_plan"]["strategy"] == approved["best_strategy"]
    md = service.export(project_id, fmt="markdown")
    assert "雨夜霓虹" in md
    assert "Scores" in md


def test_revise_storyboard_keeps_research(tmp_path):
    service = _service(tmp_path)
    created = service.create(
        MovieRequest(
            title="雨夜霓虹",
            genre="科幻",
            style="cinematic",
            duration_sec=45,
            budget_cny=25000,
            footage_source="generated",
        )
    )
    before = list(created["dispatch_log"])
    project_id = created["project_id"]
    revised = service.resume(
        project_id,
        decision="revise",
        notes="镜头再短一点",
    )
    assert revised["status"] == "interrupted"
    assert revised["revision_round"] == 1
    # No research keywords => dispatch_log should not grow with research agents.
    assert revised["dispatch_log"] == before


def test_over_budget_fails(tmp_path):
    service = _service(tmp_path)
    project = service.create(
        MovieRequest(
            title="雨夜霓虹",
            genre="科幻",
            style="cinematic",
            duration_sec=90,
            budget_cny=500,
            footage_source="stock",
        )
    )
    assert project["status"] == "failed"
    assert project["error"] in {"no_viable_plan", "failed"}
