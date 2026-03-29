"""Markdown output formatting."""

from collections import defaultdict
from datetime import date

from gitglimpse.estimation import format_duration
from gitglimpse.grouping import Task


def _render_task_section(task: Task, heading_level: str = "##") -> list[str]:
    """Render a single task as a Markdown section."""
    lines: list[str] = []
    duration = format_duration(task.estimated_minutes)
    branch = task.branch or "general"
    n = len(task.commits)
    commit_word = "commit" if n == 1 else "commits"
    lines.append(f"{heading_level} {branch} \u2014 {n} {commit_word}, {duration}")
    lines.append("")

    all_files = list(dict.fromkeys(fc.path for c in task.commits for fc in c.files))
    if all_files:
        file_list = ", ".join(all_files[:6])
        suffix = ", \u2026" if len(all_files) > 6 else ""
        lines.append(f"**Files:** {file_list}{suffix}")

    lines.append(f"**Changes:** +{task.insertions} \u2212{task.deletions}")

    messages = [c.message for c in task.commits if not c.is_merge]
    if messages:
        lines.append("")
        for msg in messages:
            lines.append(f"- {msg}")

    lines.append("")
    return lines


def format_report(tasks: list[Task], report_date: date) -> str:
    """Render a daily Markdown report."""
    date_str = f"{report_date.strftime('%B')} {report_date.day}, {report_date.year}"

    lines: list[str] = [f"# Daily Report \u2014 {date_str}", ""]

    if not tasks:
        lines.append("No commits found for this period.")
        return "\n".join(lines)

    projects = sorted({t.project for t in tasks if t.project})
    multi = len(projects) > 1

    if multi:
        by_project: dict[str, list[Task]] = defaultdict(list)
        for task in tasks:
            by_project[task.project].append(task)

        for project in projects:
            lines.append(f"## {project}")
            lines.append("")
            for task in by_project[project]:
                lines.extend(_render_task_section(task, heading_level="###"))
    else:
        for task in tasks:
            lines.extend(_render_task_section(task, heading_level="##"))

    return "\n".join(lines)
