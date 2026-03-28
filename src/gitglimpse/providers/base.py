"""Base class and interface for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
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
    def summarize_standup(self, tasks: list[Task], report_date: date) -> str | None:
        """Return a formatted standup string, or None on failure."""

    @abstractmethod
    def summarize_report(self, tasks: list[Task], report_date: date) -> str | None:
        """Return a formatted daily report string, or None on failure."""

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
            "- Professional but brief; avoid bullet overload."
        )

    @staticmethod
    def _format_tasks_context(tasks: list[Task], report_date: date) -> str:
        """Serialise tasks into a human-readable block for the user message."""
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
            lines.append("")

        return "\n".join(lines)
