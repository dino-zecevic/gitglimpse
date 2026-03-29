"""JSON output formatting."""

import json as _json
from collections import defaultdict
from datetime import date, timedelta

from gitglimpse.grouping import Task


def _task_dict(task: Task, diff_snippets: dict | None = None, context_mode: str = "commits") -> dict:
    d: dict = {
        "summary": task.summary,
        "branch": task.branch,
        "commits": len(task.commits),
        "insertions": task.insertions,
        "deletions": task.deletions,
        "estimated_minutes": task.estimated_minutes,
    }
    if context_mode != "diffs":
        d["commit_messages"] = [c.message for c in task.commits]
    if task.project:
        d["project"] = task.project
    if diff_snippets is not None:
        lines: list[str] = []
        for commit in task.commits:
            if commit.hash in diff_snippets and len(lines) < 40:
                remaining = 40 - len(lines)
                lines.extend(diff_snippets[commit.hash].splitlines()[:remaining])
        if lines:
            d["diff_snippet"] = "\n".join(lines)
    return d


def _day_label(day: date, today: date) -> str:
    yesterday = today - timedelta(days=1)
    if day == today:
        return "Today"
    if day == yesterday:
        return "Yesterday"
    return day.strftime("%A")


def _build_days(tasks: list[Task], today: date, diff_snippets: dict | None = None, context_mode: str = "commits") -> list[dict]:
    by_day: dict[date, list[Task]] = defaultdict(list)
    for task in tasks:
        by_day[task.first_commit_time.date()].append(task)
    return [
        {
            "label": _day_label(day, today),
            "date": day.isoformat(),
            "tasks": [_task_dict(t, diff_snippets, context_mode) for t in by_day[day]],
        }
        for day in sorted(by_day)
    ]


def format_standup_json(
    tasks: list[Task],
    report_date: date,
    since_date: date | None = None,
    diff_snippets: dict | None = None,
    context_mode: str = "commits",
) -> str:
    """Render a standup update as a JSON string."""
    today = date.today()
    projects = sorted({t.project for t in tasks if t.project})
    multi = len(projects) > 1

    data: dict = {
        "date": report_date.isoformat(),
    }
    if since_date is not None:
        data["since"] = since_date.isoformat()

    if multi:
        data["multi_project"] = True
        proj_list = []
        for proj in projects:
            proj_tasks = [t for t in tasks if t.project == proj]
            proj_list.append({
                "name": proj,
                "days": _build_days(proj_tasks, today, diff_snippets, context_mode),
                "total_hours": round(sum(t.estimated_minutes for t in proj_tasks) / 60, 1),
            })
        data["projects"] = proj_list
    else:
        data["days"] = _build_days(tasks, today, diff_snippets, context_mode)

    data["total_estimated_hours"] = round(
        sum(t.estimated_minutes for t in tasks) / 60, 1
    )
    return _json.dumps(data, indent=2)


def format_week_json(
    tasks: list[Task],
    start_date: date,
    end_date: date,
    diff_snippets: dict | None = None,
    context_mode: str = "commits",
) -> str:
    """Render a weekly summary as a JSON string."""
    by_day: dict[date, list[Task]] = defaultdict(list)
    for task in tasks:
        by_day[task.first_commit_time.date()].append(task)

    days = [
        {
            "date": day.isoformat(),
            "day_name": day.strftime("%A"),
            "tasks": [_task_dict(t, diff_snippets, context_mode) for t in day_tasks],
            "total_hours": round(sum(t.estimated_minutes for t in day_tasks) / 60, 1),
        }
        for day in sorted(by_day)
        for day_tasks in [by_day[day]]
    ]

    data = {
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "days": days,
        "week_total_hours": round(sum(t.estimated_minutes for t in tasks) / 60, 1),
        "total_tasks": len(tasks),
    }
    return _json.dumps(data, indent=2)
