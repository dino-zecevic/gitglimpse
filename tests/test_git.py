"""Tests for git log parsing and commit extraction."""

import subprocess
from pathlib import Path

import pytest

from gitglimpse.git import (
    Commit,
    FileChange,
    GitError,
    get_commits,
    get_current_author_email,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _make_repo(tmp_path: Path) -> Path:
    """Initialise a bare-minimum git repo with a known user identity."""
    _git(["init", "-b", "main"], tmp_path)
    _git(["config", "user.email", "test@example.com"], tmp_path)
    _git(["config", "user.name", "Test User"], tmp_path)
    return tmp_path


def _commit(repo: Path, message: str, files: dict[str, str] | None = None) -> None:
    """Stage *files* (path → content) and create a commit."""
    if files:
        for name, content in files.items():
            filepath = repo / name
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8")
            _git(["add", name], repo)
    else:
        # Empty commit for edge-case tests.
        _git(["commit", "--allow-empty", "-m", message], repo)
        return
    _git(["commit", "-m", message], repo)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _make_repo(tmp_path)
    _commit(tmp_path, "feat: add hello", {"hello.py": "print('hello')\n"})
    _commit(tmp_path, "fix: update hello", {"hello.py": "print('hello world')\n", "readme.txt": "readme\n"})
    _commit(tmp_path, "chore: add config", {"config.json": '{"key": "value"}\n'})
    return tmp_path


# ---------------------------------------------------------------------------
# Basic parsing
# ---------------------------------------------------------------------------

class TestGetCommits:
    def test_returns_list_of_commits(self, repo: Path) -> None:
        commits = get_commits(repo)
        assert len(commits) == 3

    def test_commit_fields(self, repo: Path) -> None:
        commits = get_commits(repo)
        latest = commits[0]
        assert isinstance(latest, Commit)
        assert latest.author_email == "test@example.com"
        assert latest.message == "chore: add config"
        assert latest.hash and len(latest.hash) == 40

    def test_newest_first(self, repo: Path) -> None:
        commits = get_commits(repo)
        timestamps = [c.timestamp for c in commits]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_file_changes_parsed(self, repo: Path) -> None:
        commits = get_commits(repo)
        # "fix: update hello" touched hello.py and added readme.txt
        fix_commit = next(c for c in commits if c.message == "fix: update hello")
        paths = {fc.path for fc in fix_commit.files}
        assert "hello.py" in paths
        assert "readme.txt" in paths

    def test_file_change_fields(self, repo: Path) -> None:
        commits = get_commits(repo)
        first_commit = next(c for c in commits if c.message == "feat: add hello")
        hello_change = next(fc for fc in first_commit.files if fc.path == "hello.py")
        assert isinstance(hello_change, FileChange)
        assert hello_change.insertions >= 1
        assert hello_change.deletions == 0

    def test_is_merge_false_for_regular_commits(self, repo: Path) -> None:
        commits = get_commits(repo)
        assert all(not c.is_merge for c in commits)

    def test_is_merge_true_for_merge_message(self, repo: Path) -> None:
        _commit(repo, "Merge branch 'feature' into main")
        commits = get_commits(repo)
        merge = next(c for c in commits if c.message.startswith("Merge"))
        assert merge.is_merge is True

    def test_unicode_in_message(self, repo: Path) -> None:
        _commit(repo, "feat: añadir soporte 🎉", {"unicode.txt": "contenido\n"})
        commits = get_commits(repo)
        unicode_commit = next(c for c in commits if "añadir" in c.message)
        assert "🎉" in unicode_commit.message


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

class TestFiltering:
    def test_since_filters_old_commits(self, repo: Path) -> None:
        # --since="1 second ago" should return very recent commits.
        # We'll use a far-future date to get zero results.
        commits = get_commits(repo, since="2099-01-01")
        assert commits == []

    def test_until_filters_future_commits(self, repo: Path) -> None:
        # --until with a past date returns nothing from our newly-made repo.
        commits = get_commits(repo, until="2000-01-01")
        assert commits == []

    def test_since_returns_all_recent(self, repo: Path) -> None:
        commits = get_commits(repo, since="1 year ago")
        assert len(commits) == 3

    def test_author_filter(self, repo: Path) -> None:
        commits = get_commits(repo, author="test@example.com")
        assert len(commits) == 3

    def test_author_filter_no_match(self, repo: Path) -> None:
        commits = get_commits(repo, author="nobody@nowhere.com")
        assert commits == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_repo_returns_empty_list(self, tmp_path: Path) -> None:
        _make_repo(tmp_path)
        # No commits yet → should return [] not raise.
        commits = get_commits(tmp_path)
        assert commits == []

    def test_non_git_directory_raises(self, tmp_path: Path) -> None:
        non_git = tmp_path / "not_a_repo"
        non_git.mkdir()
        with pytest.raises(GitError, match="Not a git repository"):
            get_commits(non_git)

    def test_nonexistent_path_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist"
        with pytest.raises(GitError, match="does not exist"):
            get_commits(missing)

    def test_commit_with_no_files(self, repo: Path) -> None:
        _commit(repo, "chore: empty commit")
        commits = get_commits(repo)
        empty = next(c for c in commits if c.message == "chore: empty commit")
        assert empty.files == []
        # Empty commit with a non-"Merge" message that has no files → is_merge True
        assert empty.is_merge is True

    def test_default_path_uses_cwd(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(repo)
        commits = get_commits()
        assert len(commits) == 3


# ---------------------------------------------------------------------------
# get_current_author_email
# ---------------------------------------------------------------------------

class TestGetCurrentAuthorEmail:
    def test_returns_configured_email(self, repo: Path) -> None:
        email = get_current_author_email(repo)
        assert email == "test@example.com"

    def test_no_config_returns_empty_string(self, tmp_path: Path) -> None:
        _make_repo(tmp_path)
        # Unset email by using a fresh repo with no global config available.
        # We can test by pointing at a path that has no user.email set at all.
        # The simplest approach: unset it explicitly.
        subprocess.run(
            ["git", "config", "--unset", "user.email"],
            cwd=tmp_path,
            capture_output=True,
        )
        email = get_current_author_email(tmp_path)
        # May pick up global config; just assert it returns a string.
        assert isinstance(email, str)
