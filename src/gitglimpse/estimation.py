"""Effort estimation from commit patterns."""

from __future__ import annotations

import math
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gitglimpse.grouping import Task

_BREAK_THRESHOLD = timedelta(hours=2)
_BREAK_CAP_MINUTES = 45
_PRIOR_WORK_MINUTES = 30
_SMALL_CHANGE_LINES = 20
_SMALL_CHANGE_FLOOR_MINUTES = 30
_MINIMUM_MINUTES = 15

# Size signal for single-commit tasks (no gaps to infer effort from).
_SIZE_SIGNAL_THRESHOLD_LINES = 50
_MINUTES_PER_LINE = 0.4
_MINUTES_PER_EXTRA_FILE = 5
_SIZE_SIGNAL_CAP_MINUTES = 120

# Complexity multiplier: continuous ramp above the threshold, capped.
_COMPLEXITY_THRESHOLD_LINES = 200
_COMPLEXITY_SCALE = 0.2
_COMPLEXITY_MAX_MULTIPLIER = 1.5


def _complexity_multiplier(total_lines: int) -> float:
    """Return a continuous complexity multiplier in [1.0, _COMPLEXITY_MAX_MULTIPLIER]."""
    if total_lines <= _COMPLEXITY_THRESHOLD_LINES:
        return 1.0
    doublings = math.log2(total_lines / _COMPLEXITY_THRESHOLD_LINES)
    return min(_COMPLEXITY_MAX_MULTIPLIER, 1.0 + _COMPLEXITY_SCALE * doublings)


def _distinct_file_count(task: Task) -> int:
    """Number of distinct files touched across the task's non-merge commits."""
    return len({
        fc.path
        for c in task.commits
        if not c.is_merge
        for fc in c.files
    })


def estimate_task_duration(task: Task) -> int:
    """Estimate how long the task took in minutes.

    Rules applied in order:
    1. Merge commits contribute 0 time.
    2. First non-merge commit: add 30 min of assumed prior work.
    3. Gaps between consecutive non-merge commits:
       - gap < 2 h → add actual gap in minutes
       - gap ≥ 2 h → add capped 45 min (developer likely took a break)
    4. Weak timing (single non-merge commit, no gaps to infer from): add a
       size-based signal for changes over ~50 lines, plus a little per extra file,
       so squashed large commits aren't under-counted. Small commits are untouched.
    5. If total line changes < 20 AND any gap was ≥ 2 h: floor at 30 min
       (captures debugging sessions with little visible output).
    6. Complexity multiplier: a continuous ramp above 200 lines (≤ 1.5×).
    7. Clamp to a minimum of 15 minutes.
    """
    non_merge = [c for c in task.commits if not c.is_merge]

    if not non_merge:
        return _MINIMUM_MINUTES

    # Sort oldest → newest for gap analysis.
    ordered = sorted(non_merge, key=lambda c: c.timestamp)

    total_minutes = _PRIOR_WORK_MINUTES
    had_long_gap = False

    for i in range(1, len(ordered)):
        gap = ordered[i].timestamp - ordered[i - 1].timestamp
        if gap >= _BREAK_THRESHOLD:
            total_minutes += _BREAK_CAP_MINUTES
            had_long_gap = True
        else:
            total_minutes += gap.total_seconds() / 60

    total_lines = task.insertions + task.deletions

    # Rule 4: weak-timing size signal (single-commit tasks only).
    if len(ordered) == 1 and total_lines > _SIZE_SIGNAL_THRESHOLD_LINES:
        size_minutes = (total_lines - _SIZE_SIGNAL_THRESHOLD_LINES) * _MINUTES_PER_LINE
        size_minutes += max(0, _distinct_file_count(task) - 1) * _MINUTES_PER_EXTRA_FILE
        total_minutes += min(size_minutes, _SIZE_SIGNAL_CAP_MINUTES)

    # Rule 5: debugging floor.
    if total_lines < _SMALL_CHANGE_LINES and had_long_gap:
        total_minutes = max(total_minutes, _SMALL_CHANGE_FLOOR_MINUTES)

    # Rule 6: complexity multiplier (continuous).
    total_minutes *= _complexity_multiplier(total_lines)

    return max(_MINIMUM_MINUTES, round(total_minutes))


def format_duration(minutes: int) -> str:
    """Format a duration in minutes as a human-readable string.

    Rounds up to the nearest half-hour: ~0.5h, ~1h, ~1.5h, ~2h, …
    """
    half_hours = math.ceil(minutes / 30)
    hours = half_hours / 2
    if hours == int(hours):
        return f"~{int(hours)}h"
    return f"~{hours}h"
