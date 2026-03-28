"""Template-based output formatting."""

from datetime import date

from gitglimpse.estimation import format_duration
from gitglimpse.grouping import Task

_CONTINUATION_KEYWORDS = ("fix", "bug", "issue", "error", "debug", "broken", "crash")


def _today_action(summary: str) -> str:
    if any(kw in summary.lower() for kw in _CONTINUATION_KEYWORDS):
        return f"Follow up on {summary}"
    return f"Continue working on {summary}"


def format_standup(tasks: list[Task], report_date: date) -> str:
    """Render a plain-text standup update."""
    date_str = f"{report_date.strftime('%B')} {report_date.day}, {report_date.year}"

    lines: list[str] = [f"Standup \u2014 {date_str}", ""]

    lines.append("Yesterday:")
    if not tasks:
        lines.append("  (no commits found)")
    else:
        for task in tasks:
            duration = format_duration(task.estimated_minutes)
            if task.branch:
                meta = f" ({task.branch}, {duration})"
            else:
                meta = f" ({duration})"
            lines.append(f"  \u2022 {task.summary}{meta}")

    lines.append("")
    lines.append("Today:")
    if not tasks:
        lines.append("  (nothing planned)")
    else:
        for task in tasks:
            lines.append(f"  \u2022 {_today_action(task.summary)}")

    total_hours = sum(t.estimated_minutes for t in tasks) / 60
    lines.extend(["", f"Total estimated time: {total_hours:.1f}h"])

    return "\n".join(lines)
