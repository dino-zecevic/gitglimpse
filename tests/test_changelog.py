"""Tests for changelog: classification, formatters, and git range helpers."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gitglimpse.formatters.changelog import (
    build_sections,
    format_changelog_json,
    format_changelog_markdown,
    format_changelog_template,
)
from gitglimpse.git import Commit, FileChange, get_commits_in_range, get_latest_tag
from gitglimpse.grouping import (
    changelog_subject,
    classify_commit_type,
    is_breaking_change,
)

_BASE = datetime(2026, 3, 28, 9, 0, 0, tzinfo=timezone.utc)


def _commit(message: str, is_merge: bool = False) -> Commit:
    return Commit(
        hash="abc1234" + "0" * 33,
        author_email="dev@example.com",
        message=message,
        timestamp=_BASE,
        branches=["main"],
        files=[FileChange("src/x.py", 1, 0)],
        is_merge=is_merge,
    )


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class TestClassifyCommitType:
    @pytest.mark.parametrize("message,expected", [
        ("feat: add login", "feat"),
        ("fix(auth): handle null token", "fix"),
        ("FEAT: shout", "feat"),
        ("perf: speed up", "perf"),
        ("docs: update readme", "docs"),
        ("chore: bump", "chore"),
        ("refactor!: drop old api", "refactor"),
        ("random commit message", "other"),
        ("gitglimpse: not a conventional type", "other"),
        ("wip", "other"),
    ])
    def test_classify(self, message: str, expected: str) -> None:
        assert classify_commit_type(message) == expected


class TestChangelogSubject:
    def test_strips_known_prefix(self) -> None:
        assert changelog_subject("feat: add login") == "add login"

    def test_strips_scope(self) -> None:
        assert changelog_subject("fix(auth): handle token") == "handle token"

    def test_keeps_unknown_prefix(self) -> None:
        assert changelog_subject("gitglimpse: structured context") == "gitglimpse: structured context"

    def test_no_prefix_unchanged(self) -> None:
        assert changelog_subject("just a message") == "just a message"

    def test_uses_first_line_only(self) -> None:
        assert changelog_subject("feat: add login\n\nbody text") == "add login"


class TestBreakingChange:
    def test_bang_marker(self) -> None:
        assert is_breaking_change("feat!: drop v1") is True

    def test_scope_bang_marker(self) -> None:
        assert is_breaking_change("feat(api)!: drop v1") is True

    def test_footer_marker(self) -> None:
        assert is_breaking_change("feat: x\n\nBREAKING CHANGE: removed y") is True

    def test_not_breaking(self) -> None:
        assert is_breaking_change("feat: add thing") is False


# ---------------------------------------------------------------------------
# Section building
# ---------------------------------------------------------------------------

class TestBuildSections:
    def test_groups_and_orders(self) -> None:
        commits = [
            _commit("fix: bug a"),
            _commit("feat: feature a"),
            _commit("chore: cleanup"),
        ]
        sections = build_sections(commits)
        keys = [key for key, _heading, _entries in sections]
        # feat before fix before chore (CHANGELOG_SECTIONS order)
        assert keys == ["feat", "fix", "chore"]

    def test_skips_merges(self) -> None:
        commits = [_commit("Merge branch 'x'", is_merge=True), _commit("feat: real")]
        sections = build_sections(commits)
        assert len(sections) == 1
        assert sections[0][0] == "feat"

    def test_dedupes_identical_subjects(self) -> None:
        commits = [_commit("feat: same"), _commit("feat: same")]
        sections = build_sections(commits)
        entries = sections[0][2]
        assert len(entries) == 1

    def test_empty(self) -> None:
        assert build_sections([]) == []


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

class TestFormatters:
    def test_json_structure(self) -> None:
        commits = [_commit("feat: a"), _commit("fix: b")]
        data = json.loads(format_changelog_json(commits, "v1.0.0", "HEAD"))
        assert data["from"] == "v1.0.0"
        assert data["to"] == "HEAD"
        assert data["range"] == "v1.0.0..HEAD"
        assert data["total_changes"] == 2
        assert [s["type"] for s in data["sections"]] == ["feat", "fix"]

    def test_json_breaking(self) -> None:
        commits = [_commit("feat!: big change")]
        data = json.loads(format_changelog_json(commits, None, "HEAD"))
        assert len(data["breaking_changes"]) == 1
        assert data["from"] is None

    def test_json_filtered_count(self) -> None:
        data = json.loads(format_changelog_json([_commit("feat: a")], None, "HEAD", filtered_count=3))
        assert data["filtered_commits"] == 3

    def test_markdown_headings(self) -> None:
        commits = [_commit("feat: a"), _commit("fix: b")]
        md = format_changelog_markdown(commits, "v1.0.0", "HEAD")
        assert "## Features" in md
        assert "## Bug Fixes" in md
        assert "- a" in md

    def test_markdown_breaking_first(self) -> None:
        commits = [_commit("feat: normal"), _commit("fix!: breaking fix")]
        md = format_changelog_markdown(commits, None, "HEAD")
        assert md.index("Breaking Changes") < md.index("## Features")

    def test_markdown_empty(self) -> None:
        md = format_changelog_markdown([], None, "HEAD")
        assert "No changes found" in md

    def test_template_renders(self) -> None:
        out = format_changelog_template([_commit("feat: a")], "v1.0.0", "HEAD")
        assert "Changelog" in out
        assert "v1.0.0..HEAD" in out

    def test_ticket_in_entry(self) -> None:
        commits = [_commit("fix: thing (PROJ-12)")]
        data = json.loads(format_changelog_json(commits, None, "HEAD"))
        assert data["sections"][0]["entries"][0]["ticket"] == "PROJ-12"


# ---------------------------------------------------------------------------
# git range helpers (real repos)
# ---------------------------------------------------------------------------

def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _make_repo(tmp_path: Path) -> Path:
    _git(["init", "-b", "main"], tmp_path)
    _git(["config", "user.email", "test@example.com"], tmp_path)
    _git(["config", "user.name", "Test User"], tmp_path)
    return tmp_path


def _do_commit(repo: Path, message: str, name: str, content: str) -> None:
    (repo / name).write_text(content, encoding="utf-8")
    _git(["add", name], repo)
    _git(["commit", "-m", message], repo)


class TestGitRange:
    def test_latest_tag_none_when_untagged(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _do_commit(repo, "feat: a", "a.txt", "a")
        assert get_latest_tag(repo) is None

    def test_latest_tag(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _do_commit(repo, "feat: a", "a.txt", "a")
        _git(["tag", "v1.0.0"], repo)
        assert get_latest_tag(repo) == "v1.0.0"

    def test_range_excludes_before_tag(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _do_commit(repo, "feat: first", "a.txt", "a")
        _git(["tag", "v1.0.0"], repo)
        _do_commit(repo, "fix: second", "b.txt", "b")
        commits = get_commits_in_range(repo, "v1.0.0..HEAD")
        messages = [c.message for c in commits]
        assert messages == ["fix: second"]

    def test_full_history_default(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _do_commit(repo, "feat: a", "a.txt", "a")
        _do_commit(repo, "fix: b", "b.txt", "b")
        commits = get_commits_in_range(repo, "HEAD")
        assert len(commits) == 2
