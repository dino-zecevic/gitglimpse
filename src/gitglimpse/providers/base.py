"""Base class and interface for LLM providers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import date
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from gitglimpse.grouping import Task

# Shared stderr console for provider warnings — keeps noise off stdout.
_warn = Console(stderr=True)

_GARBAGE_PHRASES = re.compile(
    r"would you like|let me help|next steps|which would you|shall i|"
    r"here's what|current state analysis",
    re.IGNORECASE,
)
_NUMBERED_LIST_RE = re.compile(r"^\d+[.)]\s", re.MULTILINE)
_MAX_OUTPUT_LEN = 2000


def validate_llm_output(response: str) -> bool:
    """Return True if the LLM output looks like a valid standup/report."""
    if len(response) > _MAX_OUTPUT_LEN:
        return False
    if "```" in response:
        return False
    if "|---|" in response or "|:--" in response:
        return False
    header_count = sum(1 for line in response.splitlines() if line.lstrip().startswith("#"))
    if header_count > 3:
        return False
    if _GARBAGE_PHRASES.search(response):
        return False
    if len(_NUMBERED_LIST_RE.findall(response)) > 5:
        return False
    return True


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

    @abstractmethod
    def summarize_pr(
        self,
        tasks: list[Task],
        branch: str,
        base: str,
        diff_snippets: dict[str, str] | None = None,
    ) -> str | None:
        """Return a formatted PR summary, or None on failure."""

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    _CORE_PROMPT = (
        "Generate a standup update. Follow this EXACT format with no deviations:\n\n"
        "Standup — [date]\n\n"
        "[day label]:\n"
        "  • [one line describing what was done] ([branch], ~[time]h)\n\n"
        "Estimated effort: [total]h\n\n"
        "STRICT RULES:\n"
        "- Use ONLY bullet points with •\n"
        "- One bullet per task, one line each, under 100 characters\n"
        "- Include branch name and time estimate in parentheses\n"
        "- NO markdown headers (no # or ## or **)\n"
        "- NO numbered lists\n"
        "- NO bold text\n"
        "- NO code snippets or code blocks\n"
        "- NO suggestions, reviews, or recommendations\n"
        "- NO questions\n"
        "- NO commentary like 'great progress' or 'excited for what comes next'\n"
        "- NO corporate or team language — write as an individual developer\n"
        "- If multiple projects, group bullets under project name followed by colon\n"
        "- Group tasks by calendar date (Yesterday:, Friday:, Today:, etc.)\n"
        "- Output NOTHING except the standup in the exact format above"
    )

    _DIFF_ADDENDUM = (
        "\n\nThese are code diffs. No commit messages were provided. "
        "Describe what was changed in plain English. "
        "Do not analyze code quality."
    )

    _BOTH_ADDENDUM = (
        "\n\nYou have both commit messages and code diffs. "
        "Use the commit messages for intent and the diffs for specifics. "
        "Write an accurate standup."
    )

    _REPORT_PROMPT = (
        "Generate a daily report in Markdown. Use # Daily Report heading, "
        "## sections per task with branch and time, files changed, "
        "+insertions/-deletions, and a brief description. "
        "No suggestions, no reviews, no commentary. Only completed work."
    )

    _WEEK_PROMPT = (
        "Generate a weekly summary. Group by day with bullet tasks. "
        "Add Key themes (3-5 bullets) and Highlights (1-3 bullets). "
        "End with week total. No suggestions, no reviews, no commentary."
    )

    _PR_PROMPT = (
        "You are writing a pull request description. You have access to the "
        "code diffs from this branch.\n\n"
        "Write:\n"
        "1. A one-paragraph summary of what this entire branch accomplishes "
        "(not per-commit, but the overall goal)\n"
        "2. A bullet list of key changes\n"
        "3. Note any risk areas or things reviewers should pay attention to\n\n"
        "Be specific — reference actual file names, function names, and logic "
        "changes from the diffs. No generic statements like 'improved code "
        "quality'. Only describe what actually changed. "
        "Keep the total output under 300 words."
    )

    @classmethod
    def _context_addendum(cls, context_mode: str) -> str:
        if context_mode == "diffs":
            return cls._DIFF_ADDENDUM
        if context_mode == "both":
            return cls._BOTH_ADDENDUM
        return ""

    @classmethod
    def get_system_prompt(cls, context_mode: str = "commits") -> str:
        """Return system prompt for standup generation."""
        return cls._CORE_PROMPT + cls._context_addendum(context_mode)

    @classmethod
    def get_report_system_prompt(cls, context_mode: str = "commits") -> str:
        """Return system prompt for daily report generation."""
        return cls._REPORT_PROMPT + cls._context_addendum(context_mode)

    @classmethod
    def get_week_system_prompt(cls, context_mode: str = "commits") -> str:
        """Return system prompt for weekly summary generation."""
        return cls._WEEK_PROMPT + cls._context_addendum(context_mode)

    @classmethod
    def get_pr_system_prompt(cls, context_mode: str = "commits") -> str:
        """Return system prompt for PR summary generation."""
        return cls._PR_PROMPT + cls._context_addendum(context_mode)

    @staticmethod
    def _format_pr_context(
        tasks: list[Task],
        branch: str,
        base: str,
        diff_snippets: dict[str, str] | None = None,
    ) -> str:
        """Serialise PR tasks into a context block for the LLM."""
        from gitglimpse.grouping import is_vague_message

        lines = [
            f"Branch: {branch}",
            f"Base: {base}",
            f"Tasks: {len(tasks)}",
            f"Estimated effort: {sum(t.estimated_minutes for t in tasks) / 60:.1f}h",
            "",
        ]
        all_files = sorted({fc.path for t in tasks for c in t.commits for fc in c.files})
        if all_files:
            lines.append(f"Files changed: {', '.join(all_files)}")
            lines.append("")

        for i, task in enumerate(tasks, 1):
            lines.append(f"Task {i}: {task.summary}")
            lines.append(f"  Branch: {task.branch}")
            lines.append(f"  Commits: {len(task.commits)}")
            lines.append(f"  +{task.insertions} insertions, \u2212{task.deletions} deletions")
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
    def _format_tasks_context(
        tasks: list[Task],
        report_date: date,
        diff_snippets: dict[str, str] | None = None,
    ) -> str:
        """Serialise tasks into a human-readable block for the user message."""
        from gitglimpse.grouping import is_vague_message

        date_str = f"{report_date.strftime('%B')} {report_date.day}, {report_date.year}"
        projects = sorted({t.project for t in tasks if t.project})
        lines = [f"Date: {date_str}", f"Tasks: {len(tasks)}", ""]
        if len(projects) > 1:
            lines.append(
                "Note: The following tasks span multiple projects/repositories. "
                "Correlate related work across projects when possible."
            )
            lines.append(f"Projects: {', '.join(projects)}")
            lines.append("")

        for i, task in enumerate(tasks, 1):
            branch = task.branch or "(no branch)"
            project_prefix = f"[{task.project}] " if task.project and len(projects) > 1 else ""
            lines.append(f"Task {i}: {project_prefix}{task.summary}")
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
        projects = sorted({t.project for t in tasks if t.project})
        lines = [
            f"Period: {start_str} to {end_str}",
            f"Total tasks: {len(tasks)}",
            f"Estimated effort: {sum(t.estimated_minutes for t in tasks) / 60:.1f}h",
            "",
        ]
        if len(projects) > 1:
            lines.append(
                "Note: The following tasks span multiple projects/repositories. "
                "Correlate related work across projects when possible."
            )
            lines.append(f"Projects: {', '.join(projects)}")
            lines.append("")

        by_day: dict[date, list[Task]] = defaultdict(list)
        for task in tasks:
            by_day[task.first_commit_time.date()].append(task)

        for day in sorted(by_day):
            day_tasks = by_day[day]
            lines.append(f"## {day.strftime('%A, %B')} {day.day}")
            for i, task in enumerate(day_tasks, 1):
                branch = task.branch or "(no branch)"
                project_prefix = f"[{task.project}] " if task.project and len(projects) > 1 else ""
                lines.append(f"Task {i}: {project_prefix}{task.summary}")
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

    @staticmethod
    def _format_diff_only_context(
        tasks: list[Task],
        report_date: date,
        diff_snippets: dict[str, str],
    ) -> str:
        """Serialise tasks with diffs only — no commit messages."""
        date_str = f"{report_date.strftime('%B')} {report_date.day}, {report_date.year}"
        lines = [f"Date: {date_str}", f"Tasks: {len(tasks)}", ""]

        for i, task in enumerate(tasks, 1):
            branch = task.branch or "(no branch)"
            lines.append(f"Task {i}:")
            lines.append(f"  Branch: {branch}")
            lines.append(f"  +{task.insertions} insertions, -{task.deletions} deletions")
            lines.append(f"  Estimated: {task.estimated_minutes} minutes")
            files = sorted({f.path for c in task.commits for f in c.files})
            if files:
                lines.append(f"  Files changed: {', '.join(files)}")
            task_diff_lines = 0
            for commit in task.commits:
                if commit.hash in diff_snippets and task_diff_lines < 60:
                    lines.append(f"  Diff ({commit.hash[:7]}):")
                    for dl in diff_snippets[commit.hash].splitlines():
                        if task_diff_lines >= 60:
                            lines.append("    ... (truncated)")
                            break
                        lines.append(f"    {dl}")
                        task_diff_lines += 1
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_diff_only_week_context(
        tasks: list[Task],
        start_date: date,
        end_date: date,
        diff_snippets: dict[str, str],
    ) -> str:
        """Serialise a week's tasks with diffs only — no commit messages."""
        start_str = f"{start_date.strftime('%B')} {start_date.day}, {start_date.year}"
        end_str = f"{end_date.strftime('%B')} {end_date.day}, {end_date.year}"
        lines = [
            f"Period: {start_str} to {end_str}",
            f"Total tasks: {len(tasks)}",
            f"Estimated effort: {sum(t.estimated_minutes for t in tasks) / 60:.1f}h",
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
                lines.append(f"Task {i}:")
                lines.append(f"  Branch: {branch}")
                lines.append(
                    f"  +{task.insertions} insertions, -{task.deletions} deletions"
                )
                lines.append(f"  Estimated: {task.estimated_minutes} minutes")
                files = sorted({f.path for c in task.commits for f in c.files})
                if files:
                    lines.append(f"  Files changed: {', '.join(files)}")
                task_diff_lines = 0
                for commit in task.commits:
                    if commit.hash in diff_snippets and task_diff_lines < 60:
                        lines.append(f"  Diff ({commit.hash[:7]}):")
                        for dl in diff_snippets[commit.hash].splitlines():
                            if task_diff_lines >= 60:
                                lines.append("    ... (truncated)")
                                break
                            lines.append(f"    {dl}")
                            task_diff_lines += 1
            lines.append("")

        return "\n".join(lines)
