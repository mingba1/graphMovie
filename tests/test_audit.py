from graphmovie.llm import build_storyboard
from graphmovie.nodes.audit import audit_agent
from graphmovie.nodes.budget import budget_agent
from graphmovie.tools import build_tools


def _base_state():
    tools = build_tools()
    request = {
        "title": "雨夜霓虹",
        "genre": "科幻",
        "style": "cinematic",
        "duration_sec": 40,
        "budget_cny": 20000,
        "pace": "balanced",
        "footage_source": "generated",
        "project_id": "audit-1",
        "interests": [],
    }
    return {
        "request": request,
        "catalog": tools.catalog.search(style="cinematic", genre="科幻"),
        "cast": tools.cast.search(genre="科幻", style="cinematic"),
        "audio": tools.audio.search(style="cinematic"),
        "locations": tools.location.search(style="cinematic", genre="科幻"),
        "footage": [],
        "strategy": "balanced",
        "attempt": 1,
    }


def test_hallucination_blames_storyboard_agent():
    state = _base_state()
    draft = build_storyboard(
        request=state["request"],
        strategy="balanced",
        catalog=state["catalog"],
        cast=state["cast"],
        audio=state["audio"],
        locations=state["locations"],
        footage=[],
        inject_hallucination=True,
    ).model_dump()
    state["draft"] = draft
    priced_cmd = budget_agent(state)
    priced = priced_cmd.update["priced_routes"][0]
    audit_state = {**state, "priced": priced, "attempt": 1}
    result = audit_agent(audit_state)
    report = result.update["audits"][0]
    assert "不存在的月球歌剧院" in report["hallucinations"]
    assert report["agent_blame"]["storyboard_agent"]
    assert report["decision"] in {"retry", "discard"}


def test_price_error_blames_budget_agent():
    state = _base_state()
    draft = build_storyboard(
        request=state["request"],
        strategy="balanced",
        catalog=state["catalog"],
        cast=state["cast"],
        audio=state["audio"],
        locations=state["locations"],
        footage=[],
    ).model_dump()
    state["draft"] = draft
    priced_cmd = budget_agent(state)
    priced = priced_cmd.update["priced_routes"][0]
    # Corrupt catalog_price after budgeting to simulate a pricing bug.
    priced["shots"][0]["catalog_price"] = int(priced["shots"][0]["catalog_price"] or 0) + 999
    result = audit_agent({**state, "priced": priced, "attempt": 1})
    report = result.update["audits"][0]
    assert report["price_errors"]
    assert report["agent_blame"]["budget_agent"]
    assert not report["hallucinations"]
