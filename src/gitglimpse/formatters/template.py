"""Template-based output formatting."""

from collections import defaultdict
from datetime import date, timedelta

from gitglimpse.estimation import format_duration
from gitglimpse.grouping import Task


def _day_label(day: date, today: date) -> str:
    """Return a human-friendly label for *day* relative to *today*."""
    yesterday = today - timedelta(days=1)
    if day == today:
        return "Today"
    if day == yesterday:
        return "Yesterday"
    return day.strftime("%A")


def _render_task_bullet(task: Task, inline_project: bool = False) -> str:
    duration = format_duration(task.estimated_minutes)
    parts = []
    if inline_project and task.project:
        parts.append(f"{task.project}/{task.branch}" if task.branch else task.project)
    elif task.branch:
        parts.append(task.branch)
    parts.append(duration)
    meta = f" ({', '.join(parts)})"
    return f"  \u2022 {task.summary}{meta}"


def format_standup(tasks: list[Task], report_date: date, group_by: str = "project") -> str:
    """Render a plain-text standup update."""
    date_str = f"{report_date.strftime('%B')} {report_date.day}, {report_date.year}"
    lines: list[str] = [f"Standup \u2014 {date_str}", ""]

    if not tasks:
        lines.append("(no commits found)")
        lines.extend(["", "Total estimated time: 0.0h"])
        return "\n".join(lines)

    projects = sorted({t.project for t in tasks if t.project})
    multi = len(projects) > 1
    today = date.today()

    if multi and group_by == "task":
        # Flat list with project name inline in each bullet.
        by_day: dict[date, list[Task]] = defaultdict(list)
        for task in tasks:
            by_day[task.first_commit_time.date()].append(task)

        for day in sorted(by_day):
            label = _day_label(day, today)
            lines.append(f"{label}:")
            for task in by_day[day]:
                lines.append(_render_task_bullet(task, inline_project=True))
            lines.append("")

        total_hours = sum(t.estimated_minutes for t in tasks) / 60
        lines.append(f"Total estimated time: {total_hours:.1f}h across {len(projects)} projects")
    elif multi:
        # Group by project (default).
        by_project: dict[str, list[Task]] = defaultdict(list)
        for task in tasks:
            by_project[task.project].append(task)

        for project in projects:
            lines.append(f"{project}:")
            by_day = defaultdict(list)
            for task in by_project[project]:
                by_day[task.first_commit_time.date()].append(task)
            for day in sorted(by_day):
                if len(by_day) > 1:
                    label = _day_label(day, today)
                    lines.append(f"  {label}:")
                    for task in by_day[day]:
                        lines.append(f"  {_render_task_bullet(task)}")
                else:
                    for task in by_day[day]:
                        lines.append(_render_task_bullet(task))
            lines.append("")

        total_hours = sum(t.estimated_minutes for t in tasks) / 60
        lines.append(f"Total estimated time: {total_hours:.1f}h across {len(projects)} projects")
    else:
        by_day = defaultdict(list)
        for task in tasks:
            by_day[task.first_commit_time.date()].append(task)

        for day in sorted(by_day):
            label = _day_label(day, today)
            lines.append(f"{label}:")
            for task in by_day[day]:
                lines.append(_render_task_bullet(task))
            lines.append("")

        total_hours = sum(t.estimated_minutes for t in tasks) / 60
        lines.append(f"Total estimated time: {total_hours:.1f}h")

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
