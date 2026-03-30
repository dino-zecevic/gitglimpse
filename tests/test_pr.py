"""Tests for the PR command formatters and branch commit retrieval."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from gitglimpse.formatters.pr import format_pr_json, format_pr_template
from gitglimpse.git import Commit, FileChange
from gitglimpse.grouping import Task, extract_ticket_id, group_commits_into_tasks

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE = datetime(2026, 3, 28, 9, 0, 0, tzinfo=timezone.utc)


def _ts(offset_hours: float) -> datetime:
    return _BASE + timedelta(hours=offset_hours)


def _fc(path: str, ins: int = 1, dels: int = 0) -> FileChange:
    return FileChange(path=path, insertions=ins, deletions=dels)


def _commit(
    message: str,
    offset_hours: float = 0,
    branches: list[str] | None = None,
    files: list[FileChange] | None = None,
    is_merge: bool = False,
) -> Commit:
    return Commit(
        hash="a" * 40,
        author_email="dev@example.com",
        message=message,
        timestamp=_ts(offset_hours),
        branches=branches or ["feature/PROJ-123-auth"],
        files=files or [_fc("src/auth.py", 10, 2)],
        is_merge=is_merge,
    )


def _sample_tasks() -> list[Task]:
    commits = [
        _commit("feat: add auth middleware", offset_hours=0, files=[
            _fc("src/auth.py", 50, 5),
            _fc("src/middleware.py", 30, 10),
        ]),
        _commit("feat: add login endpoint", offset_hours=1, files=[
            _fc("src/routes/login.py", 40, 0),
            _fc("tests/test_login.py", 20, 0),
        ]),
    ]
    return group_commits_into_tasks(commits)


# ---------------------------------------------------------------------------
# format_pr_template
# ---------------------------------------------------------------------------

class TestFormatPrTemplate:
    def test_contains_header(self) -> None:
        tasks = _sample_tasks()
        output = format_pr_template(tasks, "feature/PROJ-123-auth", "main")
        assert "PR Summary" in output
        assert "main" in output

    def test_contains_summary_section(self) -> None:
        tasks = _sample_tasks()
        output = format_pr_template(tasks, "feature/PROJ-123-auth", "main")
        assert "Summary" in output

    def test_contains_changes_section(self) -> None:
        tasks = _sample_tasks()
        output = format_pr_template(tasks, "feature/PROJ-123-auth", "main")
        assert "Changes" in output

    def test_contains_files_changed_section(self) -> None:
        tasks = _sample_tasks()
        output = format_pr_template(tasks, "feature/PROJ-123-auth", "main")
        assert "Files changed" in output
        assert "src/auth.py" in output

    def test_contains_stats_section(self) -> None:
        tasks = _sample_tasks()
        output = format_pr_template(tasks, "feature/PROJ-123-auth", "main")
        assert "Stats" in output
        assert "commit" in output

    def test_ticket_shown_when_present(self) -> None:
        tasks = _sample_tasks()
        output = format_pr_template(
            tasks, "feature/PROJ-123-auth", "main", ticket="PROJ-123",
        )
        assert "PROJ-123" in output
        assert "Ticket" in output

    def test_no_ticket_line_when_absent(self) -> None:
        tasks = _sample_tasks()
        output = format_pr_template(tasks, "feat/auth", "main", ticket=None)
        assert "Ticket" not in output

    def test_files_grouped_by_directory(self) -> None:
        tasks = _sample_tasks()
        output = format_pr_template(tasks, "feature/PROJ-123-auth", "main")
        # "src/" directory group and "tests/" directory group should appear.
        assert "src/" in output
        assert "tests/" in output

    def test_empty_tasks(self) -> None:
        output = format_pr_template([], "feat/empty", "main")
        assert "PR Summary" in output
        assert "0 commits" in output


# ---------------------------------------------------------------------------
# format_pr_json
# ---------------------------------------------------------------------------

class TestFormatPrJson:
    def test_valid_json(self) -> None:
        tasks = _sample_tasks()
        result = json.loads(format_pr_json(tasks, "feature/PROJ-123-auth", "main"))
        assert isinstance(result, dict)

    def test_required_fields(self) -> None:
        tasks = _sample_tasks()
        data = json.loads(format_pr_json(
            tasks, "feature/PROJ-123-auth", "main", ticket="PROJ-123",
        ))
        assert data["branch"] == "feature/PROJ-123-auth"
        assert data["base"] == "main"
        assert data["ticket"] == "PROJ-123"
        assert isinstance(data["summary"], str)
        assert isinstance(data["tasks"], list)
        assert isinstance(data["files_changed"], list)
        assert isinstance(data["total_insertions"], int)
        assert isinstance(data["total_deletions"], int)
        assert isinstance(data["total_commits"], int)
        assert isinstance(data["estimated_hours"], float)

    def test_ticket_null_when_absent(self) -> None:
        tasks = _sample_tasks()
        data = json.loads(format_pr_json(tasks, "feat/auth", "main"))
        assert data["ticket"] is None

    def test_filtered_count_included(self) -> None:
        tasks = _sample_tasks()
        data = json.loads(format_pr_json(
            tasks, "feat/auth", "main", filtered_count=3,
        ))
        assert data["filtered_commits"] == 3

    def test_filtered_count_omitted_when_zero(self) -> None:
        tasks = _sample_tasks()
        data = json.loads(format_pr_json(
            tasks, "feat/auth", "main", filtered_count=0,
        ))
        assert "filtered_commits" not in data

    def test_files_changed_lists_unique_paths(self) -> None:
        tasks = _sample_tasks()
        data = json.loads(format_pr_json(tasks, "feat/auth", "main"))
        files = data["files_changed"]
        assert len(files) == len(set(files))
        assert "src/auth.py" in files

    def test_task_objects_have_expected_keys(self) -> None:
        tasks = _sample_tasks()
        data = json.loads(format_pr_json(tasks, "feat/auth", "main"))
        task_obj = data["tasks"][0]
        assert "summary" in task_obj
        assert "branch" in task_obj
        assert "ticket" in task_obj
        assert "commits" in task_obj
        assert "commit_messages" in task_obj

    def test_empty_tasks_json(self) -> None:
        data = json.loads(format_pr_json([], "feat/empty", "main"))
        assert data["total_commits"] == 0
        assert data["tasks"] == []
        assert data["files_changed"] == []


# ---------------------------------------------------------------------------
# Integration: ticket extraction flows into PR output
# ---------------------------------------------------------------------------

class TestPrTicketIntegration:
    def test_ticket_from_branch_in_template(self) -> None:
        tasks = _sample_tasks()
        ticket = extract_ticket_id("feature/PROJ-123-auth")
        output = format_pr_template(tasks, "feature/PROJ-123-auth", "main", ticket=ticket)
        assert "PROJ-123" in output

    def test_ticket_from_branch_in_json(self) -> None:
        tasks = _sample_tasks()
        ticket = extract_ticket_id("feature/PROJ-123-auth")
        data = json.loads(format_pr_json(
            tasks, "feature/PROJ-123-auth", "main", ticket=ticket,
        ))
        assert data["ticket"] == "PROJ-123"

    def test_no_ticket_branch_in_json(self) -> None:
        tasks = _sample_tasks()
        ticket = extract_ticket_id("feat/add-search")
        data = json.loads(format_pr_json(
            tasks, "feat/add-search", "main", ticket=ticket,
        ))
        assert data["ticket"] is None
