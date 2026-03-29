"""Template-based output formatting."""

from collections import defaultdict
from datetime import date, timedelta

from rich.markup import escape as _escape

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
    summary = _escape(task.summary)
    branch = _escape(task.branch) if task.branch else None
    project = _escape(task.project) if task.project else None

    parts = []
    if inline_project and project:
        parts.append(f"[bold magenta]{project}[/bold magenta]/{branch}" if branch else f"[bold magenta]{project}[/bold magenta]")
    elif branch:
        parts.append(branch)
    parts.append(duration)
    meta = f" ({', '.join(parts)})"
    return f"  [yellow]\u2022[/yellow] {summary}[dim]{meta}[/dim]"


def format_standup(tasks: list[Task], report_date: date, group_by: str = "project") -> str:
    """Render a plain-text standup update."""
    date_str = f"{report_date.strftime('%B')} {report_date.day}, {report_date.year}"
    lines: list[str] = [f"[bold yellow]Standup \u2014 {date_str}[/bold yellow]", ""]

    if not tasks:
        lines.append("(no commits found)")
        lines.extend(["", "[dim]Total estimated time:[/dim] [green]0.0h[/green]"])
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
            lines.append(f"[blue]{label}:[/blue]")
            for task in by_day[day]:
                lines.append(_render_task_bullet(task, inline_project=True))
            lines.append("")

        total_hours = sum(t.estimated_minutes for t in tasks) / 60
        lines.append(f"[dim]Total estimated time:[/dim] [green]{total_hours:.1f}h[/green] [dim]across {len(projects)} projects[/dim]")
    elif multi:
        # Group by project (default).
        by_project: dict[str, list[Task]] = defaultdict(list)
        for task in tasks:
            by_project[task.project].append(task)

        for project in projects:
            lines.append(f"[bold magenta]{_escape(project)}:[/bold magenta]")
            by_day = defaultdict(list)
            for task in by_project[project]:
                by_day[task.first_commit_time.date()].append(task)
            for day in sorted(by_day):
                if len(by_day) > 1:
                    label = _day_label(day, today)
                    lines.append(f"  [blue]{label}:[/blue]")
                    for task in by_day[day]:
                        lines.append(f"  {_render_task_bullet(task)}")
                else:
                    for task in by_day[day]:
                        lines.append(_render_task_bullet(task))
            lines.append("")

        total_hours = sum(t.estimated_minutes for t in tasks) / 60
        lines.append(f"[dim]Total estimated time:[/dim] [green]{total_hours:.1f}h[/green] [dim]across {len(projects)} projects[/dim]")
    else:
        by_day = defaultdict(list)
        for task in tasks:
            by_day[task.first_commit_time.date()].append(task)

        for day in sorted(by_day):
            label = _day_label(day, today)
            lines.append(f"[blue]{label}:[/blue]")
            for task in by_day[day]:
                lines.append(_render_task_bullet(task))
            lines.append("")

        total_hours = sum(t.estimated_minutes for t in tasks) / 60
        lines.append(f"[dim]Total estimated time:[/dim] [green]{total_hours:.1f}h[/green]")

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

    lines: list[str] = [f"[bold yellow]Weekly Summary \u2014 {header_date}[/bold yellow]", ""]

    if not tasks:
        lines.append("  (no commits found)")
        lines.extend(["", "[dim]Week total:[/dim] [green]0.0h[/green] [dim]across 0 tasks[/dim]"])
        return "\n".join(lines)

    by_day: dict[date, list[Task]] = defaultdict(list)
    for task in tasks:
        by_day[task.first_commit_time.date()].append(task)

    week_minutes = sum(t.estimated_minutes for t in tasks)

    for day in sorted(by_day):
        day_tasks = by_day[day]
        day_label = f"{day.strftime('%A')} ({day.strftime('%B')} {day.day})"
        lines.append(f"[blue]{day_label}:[/blue]")
        for task in day_tasks:
            duration = format_duration(task.estimated_minutes)
            lines.append(f"  [yellow]\u2022[/yellow] {_escape(task.summary)} [dim]({duration})[/dim]")
        day_hours = sum(t.estimated_minutes for t in day_tasks) / 60
        lines.append(f"  [dim]Day total:[/dim] [green]{day_hours:.1f}h[/green]")
        lines.append("")

    n = len(tasks)
    lines.append(f"[dim]Week total:[/dim] [green]{week_minutes / 60:.1f}h[/green] [dim]across {n} task{'s' if n != 1 else ''}[/dim]")
    return "\n".join(lines)
