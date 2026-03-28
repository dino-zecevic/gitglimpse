"""Markdown output formatting."""

from datetime import date

from gitglimpse.estimation import format_duration
from gitglimpse.grouping import Task


def format_report(tasks: list[Task], report_date: date) -> str:
    """Render a daily Markdown report."""
    date_str = f"{report_date.strftime('%B')} {report_date.day}, {report_date.year}"

    lines: list[str] = [f"# Daily Report \u2014 {date_str}", ""]

    if not tasks:
        lines.append("No commits found for this period.")
        return "\n".join(lines)

    for task in tasks:
        duration = format_duration(task.estimated_minutes)
        branch = task.branch or "unknown"
        n = len(task.commits)
        commit_word = "commit" if n == 1 else "commits"
        lines.append(f"## {branch} \u2014 {n} {commit_word}, {duration}")
        lines.append("")

        # Unique files, capped for readability.
        all_files = list(dict.fromkeys(fc.path for c in task.commits for fc in c.files))
        if all_files:
            file_list = ", ".join(all_files[:6])
            suffix = ", …" if len(all_files) > 6 else ""
            lines.append(f"**Files:** {file_list}{suffix}")

        lines.append(f"**Changes:** +{task.insertions} \u2212{task.deletions}")

        messages = [c.message for c in task.commits if not c.is_merge]
        if messages:
            lines.append("")
            for msg in messages:
                lines.append(f"- {msg}")

        lines.append("")

    return "\n".join(lines)
