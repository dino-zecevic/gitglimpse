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

# ---------------------------------------------------------------------------
# Noise filtering
# ---------------------------------------------------------------------------

_NOISE_FILE_NAMES: frozenset[str] = frozenset({
    "package-lock.json", "yarn.lock", "poetry.lock", "Pipfile.lock",
    "go.sum", "pnpm-lock.yaml",
    ".prettierrc", ".prettierignore", ".eslintrc", ".eslintrc.json",
    ".eslintrc.js", ".editorconfig", ".stylelintrc",
    ".DS_Store",
})

_NOISE_FILE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\.min\.js$"),
    re.compile(r"\.min\.css$"),
    re.compile(r"\.map$"),
    re.compile(r"\.github/workflows/.*\.ya?ml$"),
    re.compile(r"\.pyc$"),
    re.compile(r"__pycache__/"),
]

_NOISE_MSG_STARTSWITH = ("merge branch", "merge pull request", "bump")

_NOISE_MSG_CONTAINS = ("bump version", "bump dependencies")

_NOISE_MSG_KEYWORDS: frozenset[str] = frozenset({
    "run formatter", "lint fix", "auto-format", "format code",
    "apply formatting", "prettier", "eslint fix",
    "update lock file", "update lockfile", "regenerate lock",
})

_NOISE_MSG_EXACT: frozenset[str] = frozenset({"lint", "format", "formatting"})


def _is_noise_file(path: str) -> bool:
    """Return True if a file path matches a noise pattern."""
    name = Path(path).name
    if name in _NOISE_FILE_NAMES:
        return True
    return any(p.search(path) for p in _NOISE_FILE_PATTERNS)


def _is_noise_message(message: str) -> bool:
    """Return True if a commit message matches a noise pattern."""
    msg = message.strip().lower()
    if msg in _NOISE_MSG_EXACT:
        return True
    if msg.startswith(_NOISE_MSG_STARTSWITH):
        return True
    if any(kw in msg for kw in _NOISE_MSG_CONTAINS):
        return True
    if any(kw in msg for kw in _NOISE_MSG_KEYWORDS):
        return True
    return False


def filter_noise_commits(commits: list[Commit]) -> list[Commit]:
    """Remove low-value noise commits (merges, formatting, lock files, etc.).

    A commit is excluded if:
    - Its message matches known noise patterns, OR
    - ALL of its changed files match noise file patterns.

    Commits with a mix of noise and real files are kept.
    """
    filtered: list[Commit] = []
    for commit in commits:
        if _is_noise_message(commit.message):
            continue
        if commit.files and all(_is_noise_file(fc.path) for fc in commit.files):
            continue
        filtered.append(commit)
    return filtered

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


def is_vague_message(message: str) -> bool:
    """Public wrapper around ``_is_vague`` for use outside this module."""
    return _is_vague(message)


_SEMANTIC_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?:^|/)tests?/|test_[^/]+\.py$|_test\.py$", re.IGNORECASE), "Added tests"),
    (re.compile(r"(?:^|/)migrations?/|\.sql$", re.IGNORECASE), "Database migration"),
    (
        re.compile(
            r"(?:^|/)(?:config|settings|\.env)[^/]*$"
            r"|\.(?:toml|ya?ml|ini|cfg|env)$",
            re.IGNORECASE,
        ),
        "Configuration changes",
    ),
    (re.compile(r"(?:^|/)docs?/|\.md$", re.IGNORECASE), "Documentation updates"),
]


def _semantic_label(paths: list[str]) -> str | None:
    """Return a semantic label if the majority of paths match a known pattern."""
    if not paths:
        return None
    for pattern, label in _SEMANTIC_RULES:
        if sum(1 for p in paths if pattern.search(p)) > len(paths) / 2:
            return label
    return None


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

    # Attempt a semantic label from well-known path patterns.
    label = _semantic_label(all_paths)
    if label:
        return label

    mentioned: list[str] = []
    if dirs:
        # Highest-frequency directories first, at most 2.
        unique_dirs = sorted(set(dirs), key=dirs.count, reverse=True)
        mentioned.extend(f"{d}/" for d in unique_dirs[:2])
    remaining = 2 - len(mentioned)
    if bare_files and remaining > 0:
        mentioned.extend(bare_files[:remaining])

    return "Changes in " + ", ".join(mentioned) if mentioned else "Various changes"


# ---------------------------------------------------------------------------
# Ticket ID extraction
# ---------------------------------------------------------------------------

_JIRA_RE = re.compile(r"([A-Z]{2,10}-\d+)")
_GH_ISSUE_RE = re.compile(r"(?:#|gh-)(\d+)", re.IGNORECASE)


def extract_ticket_id(branch: str) -> str | None:
    """Extract a ticket ID from a branch name.

    Recognises JIRA-style (PROJ-123), GitHub issue (#15, gh-15), and
    Linear-style identifiers.  Returns the first match or None.

    GitHub-style ``gh-N`` is checked before JIRA so that ``GH-7`` is
    normalised to ``#7`` rather than treated as a two-letter JIRA project.
    """
    m = _GH_ISSUE_RE.search(branch)
    if m:
        return f"#{m.group(1)}"
    m = _JIRA_RE.search(branch)
    if m:
        return m.group(1)
    return None


def _branch_key(commit: Commit) -> str:
    """Return the primary branch for a commit, or 'main' as fallback."""
    return commit.branches[0] if commit.branches else "main"


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
    project: str = ""
    ticket: str | None = None


def _build_task(branch: str, commits: list[Commit], project: str = "") -> Task:
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
        project=project,
        ticket=extract_ticket_id(branch),
    )
    task.estimated_minutes = _estimation.estimate_task_duration(task)
    return task


def group_commits_into_tasks(
    commits: list[Commit],
    project: str = "",
) -> list[Task]:
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
            tasks.append(_build_task(branch, group, project=project))

    tasks.sort(key=lambda t: t.first_commit_time)
    return tasks
