"""Template-based output formatting."""

from collections import defaultdict
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


def format_week_template(tasks: list[Task], start_date: date, end_date: date) -> str:
    """Render a plain-text weekly summary grouped by day."""
    # Header date range.
    if start_date.month == end_date.month and start_date.year == end_date.year:
        header_date = (
            f"{start_date.strftime('%B')} {start_date.day}\u2013{end_date.day}, {end_date.year}"
        )
    else:
        s = f"{start_date.strftime('%B')} {start_date.day}"
        e = f"{end_date.strftime('%B')} {end_date.day}, {end_date.year}"
        header_date = f"{s} \u2013 {e}"

    lines: list[str] = [f"Weekly Summary \u2014 {header_date}", ""]

    if not tasks:
        lines.append("  (no commits found)")
        lines.extend(["", "Week total: 0.0h across 0 tasks"])
        return "\n".join(lines)

    by_day: dict[date, list[Task]] = defaultdict(list)
    for task in tasks:
        by_day[task.first_commit_time.date()].append(task)

    week_minutes = sum(t.estimated_minutes for t in tasks)

    for day in sorted(by_day):
        day_tasks = by_day[day]
        day_label = f"{day.strftime('%A')} ({day.strftime('%B')} {day.day})"
        lines.append(f"{day_label}:")
        for task in day_tasks:
            duration = format_duration(task.estimated_minutes)
            lines.append(f"  \u2022 {task.summary} ({duration})")
        day_hours = sum(t.estimated_minutes for t in day_tasks) / 60
        lines.append(f"  Day total: {day_hours:.1f}h")
        lines.append("")

    n = len(tasks)
    lines.append(f"Week total: {week_minutes / 60:.1f}h across {n} task{'s' if n != 1 else ''}")
    return "\n".join(lines)
