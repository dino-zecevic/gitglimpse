"""Pull request summary formatting (template and JSON)."""

import json as _json
from collections import defaultdict
from pathlib import PurePosixPath

from rich.markup import escape as _escape

from gitglimpse.estimation import format_duration
from gitglimpse.grouping import Task


# ---------------------------------------------------------------------------
# Template (Rich markup) formatter
# ---------------------------------------------------------------------------

def _group_files_by_dir(tasks: list[Task]) -> dict[str, list[str]]:
    """Collect unique file paths across all tasks, grouped by top-level dir."""
    seen: set[str] = set()
    by_dir: dict[str, list[str]] = defaultdict(list)
    for task in tasks:
        for commit in task.commits:
            for fc in commit.files:
                if fc.path not in seen:
                    seen.add(fc.path)
                    parts = PurePosixPath(fc.path).parts
                    key = parts[0] if len(parts) > 1 else ""
                    by_dir[key].append(fc.path)
    return dict(by_dir)


def format_pr_template(
    tasks: list[Task],
    branch: str,
    base: str,
    ticket: str | None = None,
) -> str:
    """Render a pull request summary using Rich markup."""
    total_commits = sum(len(t.commits) for t in tasks)
    total_ins = sum(t.insertions for t in tasks)
    total_del = sum(t.deletions for t in tasks)
    total_minutes = sum(t.estimated_minutes for t in tasks)
    total_hours = total_minutes / 60

    # Header
    header = f"[bold yellow]PR Summary \u2014 {_escape(branch)} \u2192 {_escape(base)}[/bold yellow]"
    lines: list[str] = [header]
    if ticket:
        lines.append(f"[dim]Ticket: {_escape(ticket)}[/dim]")
    lines.append("")

    # Changes — per-commit detail with file names and diff stats.
    lines.append("[bold]Changes[/bold]")
    seen_messages: set[str] = set()
    for task in tasks:
        for commit in task.commits:
            if commit.is_merge or commit.message in seen_messages:
                continue
            seen_messages.add(commit.message)
            file_names = ", ".join(
                PurePosixPath(fc.path).name for fc in commit.files
            )
            ins = sum(fc.insertions for fc in commit.files)
            dels = sum(fc.deletions for fc in commit.files)
            diff_stat = f"+{ins} -{dels}" if (ins or dels) else ""
            parts = [_escape(file_names)] if file_names else []
            if diff_stat:
                parts.append(diff_stat)
            meta = f" ({', '.join(parts)})" if parts else ""
            lines.append(
                f"  [yellow]\u2022[/yellow] {_escape(commit.message)}"
                f"[dim]{meta}[/dim]"
            )
    lines.append("")

    # Files changed — flat comma-separated list.
    all_files = sorted({
        fc.path for t in tasks for c in t.commits for fc in c.files
    })
    if all_files:
        lines.append("[bold]Files changed[/bold]")
        lines.append(f"  [dim]{', '.join(_escape(f) for f in all_files)}[/dim]")
        lines.append("")

    # Stats
    lines.append("[bold]Stats[/bold]")
    lines.append(
        f"  {total_commits} commit{'s' if total_commits != 1 else ''} "
        f"[dim]\u00b7[/dim] [green]+{total_ins}[/green] / [red]-{total_del}[/red]"
    )
    lines.append(f"  Estimated effort: [green]~{total_hours:.1f}h[/green]")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------

def format_pr_json(
    tasks: list[Task],
    branch: str,
    base: str,
    ticket: str | None = None,
    filtered_count: int = 0,
    diff_snippets: dict[str, str] | None = None,
    context_mode: str = "commits",
) -> str:
    """Render a pull request summary as a JSON string."""
    all_files: list[str] = list(dict.fromkeys(
        fc.path for t in tasks for c in t.commits for fc in c.files
    ))
    total_ins = sum(t.insertions for t in tasks)
    total_del = sum(t.deletions for t in tasks)
    total_commits = sum(len(t.commits) for t in tasks)
    total_hours = round(sum(t.estimated_minutes for t in tasks) / 60, 1)

    task_dicts: list[dict] = []
    for task in tasks:
        d: dict = {
            "summary": task.summary,
            "branch": task.branch,
            "ticket": task.ticket,
            "commits": len(task.commits),
            "insertions": task.insertions,
            "deletions": task.deletions,
            "estimated_minutes": task.estimated_minutes,
        }
        if context_mode != "diffs":
            d["commit_messages"] = [c.message for c in task.commits]
        if diff_snippets is not None:
            snippet_lines: list[str] = []
            for commit in task.commits:
                if commit.hash in diff_snippets and len(snippet_lines) < 40:
                    remaining = 40 - len(snippet_lines)
                    snippet_lines.extend(
                        diff_snippets[commit.hash].splitlines()[:remaining]
                    )
            if snippet_lines:
                d["diff_snippet"] = "\n".join(snippet_lines)
        task_dicts.append(d)

    # Summary paragraph from task summaries.
    summary = ". ".join(t.summary for t in tasks) + "." if tasks else ""

    data: dict = {
        "branch": branch,
        "base": base,
        "ticket": ticket,
        "summary": summary,
        "tasks": task_dicts,
        "files_changed": all_files,
        "total_insertions": total_ins,
        "total_deletions": total_del,
        "total_commits": total_commits,
        "estimated_hours": total_hours,
        "effort_note": "rough estimate based on commit timing",
    }
    if filtered_count > 0:
        data["filtered_commits"] = filtered_count

    return _json.dumps(data, indent=2)
