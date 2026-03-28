"""Tests for duration estimation from commit patterns."""

from datetime import datetime, timedelta, timezone

import pytest

from gitglimpse.estimation import estimate_task_duration, format_duration
from gitglimpse.git import Commit, FileChange
from gitglimpse.grouping import Task

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE = datetime(2026, 3, 28, 9, 0, 0, tzinfo=timezone.utc)


def _ts(offset_hours: float) -> datetime:
    return _BASE + timedelta(hours=offset_hours)


def _fc(path: str = "src/main.py", ins: int = 1, dels: int = 0) -> FileChange:
    return FileChange(path=path, insertions=ins, deletions=dels)


def _commit(
    message: str = "feat: something",
    offset_hours: float = 0,
    files: list[FileChange] | None = None,
    is_merge: bool = False,
    branches: list[str] | None = None,
) -> Commit:
    return Commit(
        hash="a" * 40,
        author_email="dev@example.com",
        message=message,
        timestamp=_ts(offset_hours),
        branches=branches or [],
        files=files or [_fc()],
        is_merge=is_merge,
    )


def _task(
    commits: list[Commit],
    branch: str = "",
    insertions: int | None = None,
    deletions: int | None = None,
) -> Task:
    """Build a Task directly, bypassing estimation (estimated_minutes=0)."""
    ins = insertions if insertions is not None else sum(fc.insertions for c in commits for fc in c.files)
    dels = deletions if deletions is not None else sum(fc.deletions for c in commits for fc in c.files)
    ordered = sorted(commits, key=lambda c: c.timestamp)
    return Task(
        branch=branch,
        commits=commits,
        summary="test task",
        insertions=ins,
        deletions=dels,
        estimated_minutes=0,
        first_commit_time=ordered[0].timestamp,
        last_commit_time=ordered[-1].timestamp,
    )


# ---------------------------------------------------------------------------
# estimate_task_duration
# ---------------------------------------------------------------------------

class TestEstimateTaskDuration:
    def test_single_commit_returns_prior_work(self) -> None:
        task = _task([_commit(offset_hours=0)])
        assert estimate_task_duration(task) == 30

    def test_two_commits_short_gap_adds_actual_gap(self) -> None:
        # Gap = 60 min → 30 (prior) + 60 (gap) = 90
        task = _task([
            _commit(offset_hours=0),
            _commit(offset_hours=1),
        ])
        assert estimate_task_duration(task) == 90

    def test_two_commits_gap_just_under_2h(self) -> None:
        # Gap = 119 min → 30 + 119 = 149
        task = _task([
            _commit(offset_hours=0),
            _commit(offset_hours=119 / 60),
        ])
        assert estimate_task_duration(task) == 149

    def test_gap_over_2h_capped_at_45(self) -> None:
        # Gap = 3h → 30 (prior) + 45 (cap) = 75
        task = _task([
            _commit(offset_hours=0),
            _commit(offset_hours=3),
        ])
        assert estimate_task_duration(task) == 75

    def test_gap_exactly_2h_is_capped(self) -> None:
        # Exactly 2h → cap applies (≥ threshold): 30 + 45 = 75
        task = _task([
            _commit(offset_hours=0),
            _commit(offset_hours=2),
        ])
        assert estimate_task_duration(task) == 75

    def test_multiple_gaps_mixed(self) -> None:
        # Gap1 = 1h (60 min), Gap2 = 3h (capped 45 min) → 30 + 60 + 45 = 135
        task = _task([
            _commit(offset_hours=0),
            _commit(offset_hours=1),
            _commit(offset_hours=4),
        ])
        assert estimate_task_duration(task) == 135

    def test_merge_commits_contribute_zero(self) -> None:
        # Merge-only task → minimum 15
        task = _task([
            _commit(is_merge=True, offset_hours=0),
            _commit(is_merge=True, offset_hours=1),
        ])
        assert estimate_task_duration(task) == 15

    def test_merge_commit_in_middle_skipped(self) -> None:
        # Commits at 0h and 2h with a merge at 1h.
        # Non-merge: 0h and 2h → gap exactly 2h → capped → 30 + 45 = 75
        task = _task([
            _commit(offset_hours=0),
            _commit(is_merge=True, offset_hours=1),
            _commit(offset_hours=2),
        ])
        assert estimate_task_duration(task) == 75

    def test_minimum_15_minutes(self) -> None:
        task = _task([_commit(is_merge=True)])
        result = estimate_task_duration(task)
        assert result >= 15

    def test_complexity_multiplier_applied(self) -> None:
        # >200 total lines → ×1.2; single commit → 30 × 1.2 = 36
        task = _task(
            [_commit()],
            insertions=150,
            deletions=100,  # total = 250 > 200
        )
        result = estimate_task_duration(task)
        assert result == round(30 * 1.2)

    def test_complexity_multiplier_not_applied_at_boundary(self) -> None:
        # Exactly 200 lines → no multiplier (rule is >200)
        task = _task(
            [_commit()],
            insertions=100,
            deletions=100,  # total = 200, not >200
        )
        assert estimate_task_duration(task) == 30

    def test_small_changes_long_gap_floor(self) -> None:
        # < 20 total lines, gap > 2h → floor at 30.
        # 30 (prior) + 45 (capped) = 75, which is already > 30. Floor doesn't
        # reduce it but the rule ensures it won't go below 30.
        task = _task(
            [_commit(offset_hours=0), _commit(offset_hours=3)],
            insertions=5,
            deletions=5,  # total = 10 < 20
        )
        result = estimate_task_duration(task)
        assert result >= 30

    def test_result_is_integer(self) -> None:
        task = _task([_commit()])
        assert isinstance(estimate_task_duration(task), int)

    def test_non_integer_gap_rounded(self) -> None:
        # Gap = 30 min → 30 + 30 = 60
        task = _task([
            _commit(offset_hours=0),
            _commit(offset_hours=0.5),
        ])
        assert estimate_task_duration(task) == 60


# ---------------------------------------------------------------------------
# format_duration
# ---------------------------------------------------------------------------

class TestFormatDuration:
    @pytest.mark.parametrize("minutes,expected", [
        (1,   "~0.5h"),   # rounds up to first half-hour
        (15,  "~0.5h"),   # 0.25h → rounds up to 0.5h
        (30,  "~0.5h"),   # exactly 0.5h
        (31,  "~1h"),     # just over 0.5h → next half-hour = 1h
        (45,  "~1h"),     # 0.75h → rounds up to 1h
        (60,  "~1h"),     # exactly 1h
        (61,  "~1.5h"),   # just over 1h → 1.5h
        (75,  "~1.5h"),   # 1.25h → 1.5h
        (90,  "~1.5h"),   # exactly 1.5h
        (91,  "~2h"),     # just over 1.5h → 2h
        (120, "~2h"),     # exactly 2h
        (180, "~3h"),     # exactly 3h
    ])
    def test_format_duration(self, minutes: int, expected: str) -> None:
        assert format_duration(minutes) == expected

    def test_format_returns_string(self) -> None:
        assert isinstance(format_duration(60), str)

    def test_format_starts_with_tilde(self) -> None:
        assert format_duration(45).startswith("~")

    def test_format_ends_with_h(self) -> None:
        assert format_duration(90).endswith("h")
