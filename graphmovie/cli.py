from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from graphmovie.service import build_service
from graphmovie.state import MovieRequest


def _print_project(project: dict[str, Any]) -> None:
    print(json.dumps(project, ensure_ascii=False, indent=2))


def cmd_plan(args: argparse.Namespace) -> int:
    service = build_service()
    request = MovieRequest(
        title=args.title,
        genre=args.genre,
        style=args.style,
        duration_sec=args.duration,
        budget_cny=args.budget,
        pace=args.pace,
        footage_source=args.footage,
        interests=[item for item in args.interests.split(",") if item] if args.interests else [],
        delivery_date=args.delivery_date,
    )
    project = service.create(request)
    _print_project(project)

    if project.get("status") != "interrupted":
        return 0 if project.get("status") == "approved" else 1

    if args.decision:
        notes = args.notes
        resumed = service.resume(
            project["project_id"],
            decision=args.decision,
            notes=notes,
        )
        _print_project(resumed)
        return 0 if resumed.get("status") == "approved" else 1

    print(
        "\nInterrupted for human review. Resume with:\n"
        f"  python -m graphmovie resume --project-id {project['project_id']} "
        "--decision approve\n",
        file=sys.stderr,
    )
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    service = build_service()
    project = service.resume(
        args.project_id,
        decision=args.decision,
        notes=args.notes,
    )
    _print_project(project)
    return 0 if project.get("status") in {"approved", "interrupted"} else 1


def cmd_show(args: argparse.Namespace) -> int:
    service = build_service()
    project = service.get(args.project_id)
    if not project:
        print(f"project not found: {args.project_id}", file=sys.stderr)
        return 1
    _print_project(project)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    service = build_service()
    try:
        content = service.export(args.project_id, fmt=args.format)
    except KeyError:
        print(f"project not found: {args.project_id}", file=sys.stderr)
        return 1
    print(content)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="graphmovie", description="AI movie production planner")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Create a production plan")
    plan.add_argument("--title", required=True)
    plan.add_argument("--genre", required=True)
    plan.add_argument("--style", default="cinematic", choices=["cinematic", "anime", "documentary"])
    plan.add_argument("--duration", type=int, default=60)
    plan.add_argument("--budget", type=int, default=8000)
    plan.add_argument("--pace", default="balanced", choices=["relaxed", "balanced", "packed"])
    plan.add_argument("--footage", default="generated", choices=["generated", "stock"])
    plan.add_argument("--interests", default="")
    plan.add_argument("--delivery-date", default=None)
    plan.add_argument("--decision", choices=["approve", "revise"], default=None)
    plan.add_argument("--notes", default=None)
    plan.set_defaults(func=cmd_plan)

    resume = sub.add_parser("resume", help="Resume human review")
    resume.add_argument("--project-id", required=True)
    resume.add_argument("--decision", choices=["approve", "revise"], required=True)
    resume.add_argument("--notes", default=None)
    resume.set_defaults(func=cmd_resume)

    show = sub.add_parser("show", help="Show project archive")
    show.add_argument("--project-id", required=True)
    show.set_defaults(func=cmd_show)

    export = sub.add_parser("export", help="Export markdown or json")
    export.add_argument("--project-id", required=True)
    export.add_argument("--format", choices=["markdown", "json"], default="markdown")
    export.set_defaults(func=cmd_export)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
