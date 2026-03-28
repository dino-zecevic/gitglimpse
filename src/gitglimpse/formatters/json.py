"""JSON output formatting."""

import json as _json
from collections import defaultdict
from datetime import date

from gitglimpse.grouping import Task


def _task_dict(task: Task) -> dict:
    return {
        "summary": task.summary,
        "branch": task.branch,
        "commits": len(task.commits),
        "insertions": task.insertions,
        "deletions": task.deletions,
        "estimated_minutes": task.estimated_minutes,
        "commit_messages": [c.message for c in task.commits],
    }


def format_standup_json(tasks: list[Task], report_date: date) -> str:
    """Render a standup update as a JSON string."""
    data = {
        "date": report_date.isoformat(),
        "tasks": [_task_dict(t) for t in tasks],
        "total_estimated_hours": round(
            sum(t.estimated_minutes for t in tasks) / 60, 1
        ),
    }
    return _json.dumps(data, indent=2)


def format_week_json(tasks: list[Task], start_date: date, end_date: date) -> str:
    """Render a weekly summary as a JSON string."""
    by_day: dict[date, list[Task]] = defaultdict(list)
    for task in tasks:
        by_day[task.first_commit_time.date()].append(task)

    days = [
        {
            "date": day.isoformat(),
            "day_name": day.strftime("%A"),
            "tasks": [_task_dict(t) for t in day_tasks],
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
