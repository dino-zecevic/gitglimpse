"""Duration estimation from commit patterns."""

from __future__ import annotations

import math
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gitglimpse.grouping import Task

_BREAK_THRESHOLD = timedelta(hours=2)
_BREAK_CAP_MINUTES = 45
_PRIOR_WORK_MINUTES = 30
_COMPLEXITY_THRESHOLD_LINES = 200
_COMPLEXITY_MULTIPLIER = 1.2
_SMALL_CHANGE_LINES = 20
_SMALL_CHANGE_FLOOR_MINUTES = 30
_MINIMUM_MINUTES = 15


def estimate_task_duration(task: Task) -> int:
    """Estimate how long the task took in minutes.

    Rules applied in order:
    1. Merge commits contribute 0 time.
    2. First non-merge commit: add 30 min of assumed prior work.
    3. Gaps between consecutive non-merge commits:
       - gap < 2 h → add actual gap in minutes
       - gap ≥ 2 h → add capped 45 min (developer likely took a break)
    4. If total line changes < 20 AND any gap was ≥ 2 h: floor at 30 min
       (captures debugging sessions with little visible output).
    5. If total line changes > 200: multiply by 1.2× (complex work).
    6. Clamp to a minimum of 15 minutes.
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

    # Rule 4: debugging floor.
    if total_lines < _SMALL_CHANGE_LINES and had_long_gap:
        total_minutes = max(total_minutes, _SMALL_CHANGE_FLOOR_MINUTES)

    # Rule 5: complexity multiplier.
    if total_lines > _COMPLEXITY_THRESHOLD_LINES:
        total_minutes *= _COMPLEXITY_MULTIPLIER

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
