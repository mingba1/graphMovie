from __future__ import annotations

import json
from typing import Any


def to_markdown(project: dict[str, Any]) -> str:
    request = project.get("request") or {}
    plan = project.get("final_plan") or project.get("selected_plan") or {}
    scores = project.get("scores") or {}
    lines = [
        f"# {request.get('title', 'Untitled')}",
        "",
        f"- project_id: `{project.get('project_id')}`",
        f"- status: `{project.get('status')}`",
        f"- genre: {request.get('genre')}",
        f"- style: {request.get('style')}",
        f"- duration_sec: {request.get('duration_sec')}",
        f"- budget_cny: {request.get('budget_cny')}",
        f"- best_strategy: {project.get('best_strategy')}",
        "",
    ]
    if scores:
        lines.append("## Scores")
        for strategy, score in scores.items():
            lines.append(
                f"- `{strategy}`: total={score.get('total')} "
                f"cost={score.get('cost')} time={score.get('time')} "
                f"style={score.get('style_fit')} pace={score.get('pace_fit')}"
                + (f" rejected={score.get('rejected_reason')}" if score.get("rejected_reason") else "")
            )
        lines.append("")

    if plan:
        lines.extend(
            [
                f"## Plan · {plan.get('title')}",
                f"- strategy: `{plan.get('strategy')}`",
                f"- total_duration_sec: {plan.get('total_duration_sec')}",
                f"- total_cost_cny: {plan.get('total_cost_cny')}",
                "",
                "### Shots",
            ]
        )
        for idx, shot in enumerate(plan.get("shots") or [], start=1):
            lines.append(
                f"{idx}. **{shot.get('name')}** ({shot.get('duration_sec')}s, "
                f"¥{shot.get('cost_cny')}) — {shot.get('narration')}"
            )
        lines.append("")

    audits = project.get("audits") or []
    if audits:
        lines.append("## Audits")
        for audit in audits:
            lines.append(
                f"- `{audit.get('strategy')}` attempt={audit.get('attempt')} "
                f"decision={audit.get('decision')} "
                f"hallucinations={audit.get('hallucinations')} "
                f"price_errors={audit.get('price_errors')}"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def to_json(project: dict[str, Any]) -> str:
    return json.dumps(project, ensure_ascii=False, indent=2)
