"""JSON output formatting."""

import json as _json
from datetime import date

from gitglimpse.grouping import Task


def format_standup_json(tasks: list[Task], report_date: date) -> str:
    """Render a standup update as a JSON string."""
    data = {
        "date": report_date.isoformat(),
        "tasks": [
            {
                "summary": task.summary,
                "branch": task.branch,
                "commits": len(task.commits),
                "insertions": task.insertions,
                "deletions": task.deletions,
                "estimated_minutes": task.estimated_minutes,
                "commit_messages": [c.message for c in task.commits],
            }
            for task in tasks
        ],
        "total_estimated_hours": round(
            sum(t.estimated_minutes for t in tasks) / 60, 1
        ),
    }
    return _json.dumps(data, indent=2)
