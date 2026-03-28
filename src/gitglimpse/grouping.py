"""Commit grouping into logical tasks."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from gitglimpse.git import Commit
from gitglimpse import estimation as _estimation

_TASK_GAP = timedelta(hours=3)

# Single-word vague messages (lowercased for comparison).
_VAGUE_WORDS: frozenset[str] = frozenset(
    {
        "fix", "fixes", "fixed",
        "update", "updates", "updated",
        "wip", "asdf", "test", "testing",
        "changes", "change", "stuff",
        "minor", "misc", "temp",
        "cleanup", "refactor", "refactoring",
        "done", "ok", "works",
    }
)

# Multi-word patterns that are still vague.
_VAGUE_RE = re.compile(
    r"^\s*(?:fix(?:es|ed)?|update[sd]?|wip|asdf|test(?:ing)?|changes?|"
    r"stuff|minor|misc|temp(?:orary)?|cleanup|refactor(?:ing)?|done|ok|works)\s*$",
    re.IGNORECASE,
)


def _is_vague(message: str) -> bool:
    msg = message.strip()
    if len(msg) < 4:
        return True
    if msg.lower() in _VAGUE_WORDS:
        return True
    if _VAGUE_RE.match(msg):
        return True
    return False


def _best_summary(commits: list[Commit]) -> str:
    """Return the most meaningful summary for a group of commits."""
    non_vague = [
        c.message
        for c in commits
        if not c.is_merge and not _is_vague(c.message)
    ]
    if non_vague:
        return max(non_vague, key=len)

    # Fallback: derive a summary from the file paths touched.
    all_paths = [fc.path for c in commits for fc in c.files]
    if not all_paths:
        return commits[-1].message if commits else "Various changes"

    # Collect top-level directories and bare filenames.
    dirs: list[str] = []
    bare_files: list[str] = []
    for p in all_paths:
        parts = Path(p).parts
        if len(parts) > 1:
            dirs.append(parts[0])
        else:
            bare_files.append(p)

    mentioned: list[str] = []
    if dirs:
        # Highest-frequency directories first, at most 2.
        unique_dirs = sorted(set(dirs), key=dirs.count, reverse=True)
        mentioned.extend(f"{d}/" for d in unique_dirs[:2])
    remaining = 2 - len(mentioned)
    if bare_files and remaining > 0:
        mentioned.extend(bare_files[:remaining])

    return "Changes in " + ", ".join(mentioned) if mentioned else "Various changes"


def _branch_key(commit: Commit) -> str:
    """Return the primary branch for a commit, or '' if unknown."""
    return commit.branches[0] if commit.branches else ""


def _split_by_time(commits: list[Commit]) -> list[list[Commit]]:
    """Split a time-ordered commit list wherever the gap exceeds _TASK_GAP."""
    if not commits:
        return []
    groups: list[list[Commit]] = [[commits[0]]]
    for commit in commits[1:]:
        gap = commit.timestamp - groups[-1][-1].timestamp
        if gap > _TASK_GAP:
            groups.append([commit])
        else:
            groups[-1].append(commit)
    return groups


@dataclass
class Task:
    branch: str
    commits: list[Commit]
    summary: str
    insertions: int
    deletions: int
    estimated_minutes: int
    first_commit_time: datetime
    last_commit_time: datetime


def _build_task(branch: str, commits: list[Commit]) -> Task:
    """Construct a Task from an ordered list of commits (oldest → newest)."""
    insertions = sum(fc.insertions for c in commits for fc in c.files)
    deletions = sum(fc.deletions for c in commits for fc in c.files)
    task = Task(
        branch=branch,
        commits=commits,
        summary=_best_summary(commits),
        insertions=insertions,
        deletions=deletions,
        estimated_minutes=0,  # filled in below
        first_commit_time=commits[0].timestamp,
        last_commit_time=commits[-1].timestamp,
    )
    task.estimated_minutes = _estimation.estimate_task_duration(task)
    return task


def group_commits_into_tasks(commits: list[Commit]) -> list[Task]:
    """Group a list of commits into logical tasks.

    Strategy:
    1. Bucket commits by their primary branch label.
    2. Within each bucket, sort oldest-first and split wherever the gap
       between consecutive commits exceeds 3 hours.
    3. For each resulting group, build a Task with a derived summary and
       estimated duration.
    4. Return all tasks sorted by first_commit_time (oldest first).
    """
    # Bucket by branch.
    buckets: dict[str, list[Commit]] = defaultdict(list)
    for commit in commits:
        buckets[_branch_key(commit)].append(commit)

    tasks: list[Task] = []
    for branch, branch_commits in buckets.items():
        # Sort oldest → newest for gap analysis.
        ordered = sorted(branch_commits, key=lambda c: c.timestamp)
        for group in _split_by_time(ordered):
            tasks.append(_build_task(branch, group))

    tasks.sort(key=lambda t: t.first_commit_time)
    return tasks
