"""Base class and interface for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import date
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from gitglimpse.grouping import Task

# Shared stderr console for provider warnings — keeps noise off stdout.
_warn = Console(stderr=True)


class BaseLLMProvider(ABC):
    """Common interface all LLM providers must implement."""

    @abstractmethod
    def summarize_standup(
        self,
        tasks: list[Task],
        report_date: date,
        diff_snippets: dict[str, str] | None = None,
    ) -> str | None:
        """Return a formatted standup string, or None on failure."""

    @abstractmethod
    def summarize_report(
        self,
        tasks: list[Task],
        report_date: date,
        diff_snippets: dict[str, str] | None = None,
    ) -> str | None:
        """Return a formatted daily report string, or None on failure."""

    @abstractmethod
    def summarize_week(
        self,
        tasks: list[Task],
        start_date: date,
        end_date: date,
        diff_snippets: dict[str, str] | None = None,
    ) -> str | None:
        """Return a formatted weekly summary with key themes, or None on failure."""

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @classmethod
    def get_system_prompt(cls) -> str:
        """Return formatting instructions sent to the LLM as the system role."""
        return (
            "You are a developer productivity assistant that reads git commit data "
            "and writes concise, professional standup and daily report summaries.\n\n"
            "## Standup format rules\n"
            "- Begin with: Standup — <Month Day, Year>\n"
            "- Yesterday section: bullet list of tasks with branch and time estimate.\n"
            "  Example:  • Implemented OAuth2 login flow (feature/auth, ~1.5h)\n"
            "- Today section: 1–3 bullet items inferring next steps from yesterday's work.\n"
            "- End with: Total estimated time: X.Xh\n"
            "- Keep each bullet under 100 characters.\n"
            "- Do NOT invent work that isn't in the commit data.\n\n"
            "## Daily report format rules\n"
            "- Markdown with a level-1 heading: # Daily Report — <Month Day, Year>\n"
            "- One level-2 section per task group.\n"
            "- Under each section: files changed, +insertions/−deletions, and a "
            "plain-English description of what was accomplished.\n"
            "- Professional but brief; avoid bullet overload.\n\n"
            "## Weekly summary format rules\n"
            "- Plain text with a heading: Weekly Summary — <date range>\n"
            "- Group by day of week with bullet tasks per day.\n"
            "- Add a 'Key themes' section: 3–5 bullet points identifying the main "
            "areas of work across the whole week.\n"
            "- Add a 'Highlights' section: 1–3 notable accomplishments.\n"
            "- End with a week total line."
        )

    @staticmethod
    def _format_tasks_context(
        tasks: list[Task],
        report_date: date,
        diff_snippets: dict[str, str] | None = None,
    ) -> str:
        """Serialise tasks into a human-readable block for the user message."""
        from gitglimpse.grouping import is_vague_message

        date_str = f"{report_date.strftime('%B')} {report_date.day}, {report_date.year}"
        lines = [f"Date: {date_str}", f"Tasks: {len(tasks)}", ""]

        for i, task in enumerate(tasks, 1):
            branch = task.branch or "(no branch)"
            lines.append(f"Task {i}: {task.summary}")
            lines.append(f"  Branch: {branch}")
            lines.append(f"  Commits: {len(task.commits)}")
            lines.append(f"  +{task.insertions} insertions, −{task.deletions} deletions")
            lines.append(f"  Estimated: {task.estimated_minutes} minutes")
            messages = [c.message for c in task.commits if not c.is_merge]
            if messages:
                lines.append("  Commit messages:")
                for msg in messages:
                    lines.append(f"    - {msg}")
            if diff_snippets:
                for commit in task.commits:
                    if commit.hash in diff_snippets and is_vague_message(commit.message):
                        lines.append(f"  Diff for '{commit.message}':")
                        for dl in diff_snippets[commit.hash].splitlines():
                            lines.append(f"    {dl}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_week_context(
        tasks: list[Task],
        start_date: date,
        end_date: date,
        diff_snippets: dict[str, str] | None = None,
    ) -> str:
        """Serialise a week's worth of tasks grouped by day for the LLM prompt."""
        from gitglimpse.grouping import is_vague_message

        start_str = f"{start_date.strftime('%B')} {start_date.day}, {start_date.year}"
        end_str = f"{end_date.strftime('%B')} {end_date.day}, {end_date.year}"
        lines = [
            f"Period: {start_str} to {end_str}",
            f"Total tasks: {len(tasks)}",
            f"Total estimated time: {sum(t.estimated_minutes for t in tasks) / 60:.1f}h",
            "",
        ]

        by_day: dict[date, list[Task]] = defaultdict(list)
        for task in tasks:
            by_day[task.first_commit_time.date()].append(task)

        for day in sorted(by_day):
            day_tasks = by_day[day]
            lines.append(f"## {day.strftime('%A, %B')} {day.day}")
            for i, task in enumerate(day_tasks, 1):
                branch = task.branch or "(no branch)"
                lines.append(f"Task {i}: {task.summary}")
                lines.append(f"  Branch: {branch}")
                lines.append(
                    f"  +{task.insertions} insertions, \u2212{task.deletions} deletions"
                )
                lines.append(f"  Estimated: {task.estimated_minutes} minutes")
                messages = [c.message for c in task.commits if not c.is_merge]
                for msg in messages:
                    lines.append(f"    - {msg}")
                if diff_snippets:
                    for commit in task.commits:
                        if commit.hash in diff_snippets and is_vague_message(commit.message):
                            lines.append(f"  Diff for '{commit.message}':")
                            for dl in diff_snippets[commit.hash].splitlines():
                                lines.append(f"    {dl}")
            lines.append("")

        return "\n".join(lines)
