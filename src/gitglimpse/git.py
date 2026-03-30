"""Git log parsing and commit extraction."""

import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class GitError(Exception):
    """Raised when a git operation fails."""


@dataclass(frozen=True)
class FileChange:
    path: str
    insertions: int
    deletions: int


@dataclass(frozen=True)
class Commit:
    hash: str
    author_email: str
    message: str
    timestamp: datetime
    branches: list[str]
    files: list[FileChange]
    is_merge: bool

    def __hash__(self) -> int:
        return hash(self.hash)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Commit):
            return NotImplemented
        return self.hash == other.hash


def _git_bin() -> str:
    git = shutil.which("git")
    if git is None:
        raise GitError("git executable not found. Please install git.")
    return git


def _run(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        raise GitError(f"Executable not found: {args[0]}")

    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"git exited with code {result.returncode}")

    return result.stdout


def _parse_branches(refs: str) -> list[str]:
    """Extract branch names from the %D ref decoration string."""
    if not refs.strip():
        return []
    branches: list[str] = []
    for part in refs.split(","):
        part = part.strip()
        if not part or part == "HEAD":
            continue
        # "HEAD -> main" → "main"
        if part.startswith("HEAD -> "):
            part = part[len("HEAD -> "):]
        # Skip remote-tracking and tag refs
        if part.startswith("tag: "):
            continue
        branches.append(part)
    return branches


def _parse_numstat_line(line: str) -> FileChange | None:
    """Parse a single --numstat line. Returns None for binary files."""
    parts = line.split("\t", 2)
    if len(parts) != 3:
        return None
    ins_raw, del_raw, path = parts
    # Binary files show "-" for insertions/deletions
    if ins_raw == "-" or del_raw == "-":
        return FileChange(path=path, insertions=0, deletions=0)
    try:
        return FileChange(path=path, insertions=int(ins_raw), deletions=int(del_raw))
    except ValueError:
        return None


_LOG_FORMAT = "%H|%ae|%s|%ai|%D"

_HEADER_RE = re.compile(r"^[0-9a-f]{40}\|")


def _parse_raw_output(raw: str) -> list[Commit]:
    """Parse the combined --pretty + --numstat output into Commit objects.

    git log outputs:
        <header line>       ← matches _HEADER_RE
        <blank line>
        <numstat lines>     ← tab-delimited
        <blank line>
        <next header line>
        ...
    We parse line-by-line, flushing a commit when we see the next header.
    """
    commits: list[Commit] = []

    current_header: str | None = None
    current_files: list[FileChange] = []

    def _flush(header: str, files: list[FileChange]) -> None:
        parts = header.split("|", 4)
        if len(parts) < 5:
            return
        commit_hash, author_email, message, timestamp_str, refs = parts
        try:
            timestamp = datetime.fromisoformat(timestamp_str.strip())
        except ValueError:
            return
        branches = _parse_branches(refs)
        is_merge = message.startswith("Merge") or (bool(message) and not files)
        commits.append(
            Commit(
                hash=commit_hash.strip(),
                author_email=author_email.strip(),
                message=message.strip(),
                timestamp=timestamp,
                branches=branches,
                files=files,
                is_merge=is_merge,
            )
        )

    for line in raw.splitlines():
        if _HEADER_RE.match(line):
            if current_header is not None:
                _flush(current_header, current_files)
            current_header = line
            current_files = []
        elif current_header is not None and line.strip() and "\t" in line:
            fc = _parse_numstat_line(line)
            if fc is not None:
                current_files.append(fc)

    if current_header is not None:
        _flush(current_header, current_files)

    return commits


def _clean_source_ref(ref: str) -> str:
    """Turn a --source ref like 'refs/heads/main' into a clean branch name."""
    ref = ref.strip()
    if ref.startswith("refs/heads/"):
        return ref[len("refs/heads/"):]
    if ref.startswith("refs/remotes/"):
        return ref[len("refs/remotes/"):]
    if ref.startswith("refs/original/refs/heads/"):
        return ref[len("refs/original/refs/heads/"):]
    return ref


def _get_branch_map(git: str, cwd: Path) -> dict[str, str]:
    """Return a mapping of commit hash → branch name using git log --source."""
    try:
        raw = subprocess.run(
            [git, "log", "--all", "--source", "--format=%H %S"],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if raw.returncode != 0:
            return {}
    except Exception:
        return {}

    result: dict[str, str] = {}
    for line in raw.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            commit_hash, source = parts
            branch = _clean_source_ref(source)
            if branch and branch != "HEAD":
                result[commit_hash] = branch
    return result


def _get_current_branch(git: str, cwd: Path) -> str:
    """Return the current branch name, or 'main' as fallback."""
    try:
        result = subprocess.run(
            [git, "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        name = result.stdout.strip()
        return name if name and name != "HEAD" else "main"
    except Exception:
        return "main"


def get_commits(
    repo_path: Path | None = None,
    since: str | None = None,
    until: str | None = None,
    author: str | None = None,
) -> list[Commit]:
    """Return commits from the git repo at *repo_path*, newest first.

    Args:
        repo_path: Path to the git repository. Defaults to the current directory.
        since: Only commits after this date (passed directly to --since).
        until: Only commits before this date (passed directly to --until).
        author: Filter to commits by this author pattern (passed to --author).

    Raises:
        GitError: If git is not installed, repo_path is not a git repo, or
                  any other git operation fails.
    """
    git = _git_bin()
    cwd = Path(repo_path) if repo_path is not None else Path.cwd()

    if not cwd.exists():
        raise GitError(f"Path does not exist: {cwd}")

    # Verify this is actually a git repository.
    verify = subprocess.run(
        [git, "rev-parse", "--git-dir"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if verify.returncode != 0:
        raise GitError(f"Not a git repository: {cwd}")

    # Check for empty repo (no commits yet).
    head_check = subprocess.run(
        [git, "rev-parse", "HEAD"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if head_check.returncode != 0:
        return []

    cmd = [
        git,
        "log",
        f"--pretty=format:{_LOG_FORMAT}",
        "--numstat",
    ]

    if since:
        cmd.append(f"--since={since}")
    if until:
        cmd.append(f"--until={until}")
    if author:
        cmd.append(f"--author={author}")

    raw = _run(cmd, cwd=cwd)
    commits = _parse_raw_output(raw)

    # Enrich commits that have no branch decoration with source-ref data.
    branch_map = _get_branch_map(git, cwd)
    fallback_branch = _get_current_branch(git, cwd)
    enriched: list[Commit] = []
    for c in commits:
        if not c.branches:
            branch = branch_map.get(c.hash, fallback_branch)
            c = Commit(
                hash=c.hash,
                author_email=c.author_email,
                message=c.message,
                timestamp=c.timestamp,
                branches=[branch],
                files=c.files,
                is_merge=c.is_merge,
            )
        enriched.append(c)
    commits = enriched

    # Sort newest-first (git log already does this, but be explicit).
    commits.sort(key=lambda c: c.timestamp, reverse=True)
    return commits


def get_commit_diff(
    repo_path: Path | None,
    commit_hash: str,
    max_lines: int = 50,
) -> str:
    """Return a truncated unified diff for the given commit.

    Strips the commit header block (everything before the first ``diff --git``
    line) and caps output at *max_lines* diff lines to keep prompts compact.
    """
    git = _git_bin()
    cwd = Path(repo_path) if repo_path is not None else Path.cwd()
    raw = _run([git, "show", "--patch", "-U2", commit_hash], cwd=cwd)
    lines = raw.splitlines()
    # Skip the commit header; start from the first diff hunk.
    diff_start = next(
        (i for i, ln in enumerate(lines) if ln.startswith("diff --git")), 0
    )
    diff_lines = lines[diff_start:]
    if len(diff_lines) <= max_lines:
        return "\n".join(diff_lines)
    truncated = len(diff_lines) - max_lines
    return "\n".join(diff_lines[:max_lines]) + f"\n... ({truncated} more lines)"


def get_current_branch_name(repo_path: Path | None = None) -> str:
    """Return the current branch name, or 'main' if detached."""
    git = _git_bin()
    cwd = Path(repo_path) if repo_path is not None else Path.cwd()
    return _get_current_branch(git, cwd)


def get_branch_commits(
    repo_path: Path | None = None,
    base: str = "main",
) -> list[Commit]:
    """Return commits on the current branch that are not on *base*.

    Uses ``git log base..HEAD`` to find the range.  Returns newest-first.
    Raises GitError if the base ref does not exist.
    """
    git = _git_bin()
    cwd = Path(repo_path) if repo_path is not None else Path.cwd()

    if not cwd.exists():
        raise GitError(f"Path does not exist: {cwd}")

    # Verify this is a git repository.
    verify = subprocess.run(
        [git, "rev-parse", "--git-dir"],
        cwd=cwd, capture_output=True, text=True,
    )
    if verify.returncode != 0:
        raise GitError(f"Not a git repository: {cwd}")

    # Verify base ref exists.
    ref_check = subprocess.run(
        [git, "rev-parse", "--verify", base],
        cwd=cwd, capture_output=True, text=True,
    )
    if ref_check.returncode != 0:
        raise GitError(f"Base ref not found: {base}")

    cmd = [
        git, "log",
        f"--pretty=format:{_LOG_FORMAT}",
        "--numstat",
        f"{base}..HEAD",
    ]
    raw = _run(cmd, cwd=cwd)
    commits = _parse_raw_output(raw)

    # Enrich branch info.
    fallback_branch = _get_current_branch(git, cwd)
    enriched: list[Commit] = []
    for c in commits:
        if not c.branches:
            c = Commit(
                hash=c.hash,
                author_email=c.author_email,
                message=c.message,
                timestamp=c.timestamp,
                branches=[fallback_branch],
                files=c.files,
                is_merge=c.is_merge,
            )
        enriched.append(c)

    enriched.sort(key=lambda c: c.timestamp, reverse=True)
    return enriched


def get_current_author_email(repo_path: Path | None = None) -> str:
    """Return the configured git user.email for the repo.

    Returns an empty string if no email is configured.
    """
    git = _git_bin()
    cwd = Path(repo_path) if repo_path is not None else Path.cwd()

    result = subprocess.run(
        [git, "config", "user.email"],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()
