"""Tests for CLI precedence helpers and multi-project diff scoping."""

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

import gitglimpse.cli as cli
import gitglimpse.config as config
from gitglimpse.cli import (
    _SENTINEL_SINCE,
    _effective_since,
    _parse_date_bound,
    _resolve_author,
    _resolve_repo_paths,
    app,
)
from gitglimpse.git import get_commits

runner = CliRunner()


# ---------------------------------------------------------------------------
# _effective_since
# ---------------------------------------------------------------------------

class TestEffectiveSince:
    def test_cli_flag_wins(self) -> None:
        assert _effective_since("3 days ago", "yesterday") == "3 days ago"

    def test_config_value_used_when_no_cli(self) -> None:
        assert _effective_since(_SENTINEL_SINCE, "last monday") == "last monday"

    def test_smart_default_when_both_defaults(self) -> None:
        # cfg is the default "yesterday" and no CLI flag → smart weekday default.
        result = _effective_since(_SENTINEL_SINCE, "yesterday")
        assert result in {"yesterday", "last friday"}


# ---------------------------------------------------------------------------
# _resolve_author
# ---------------------------------------------------------------------------

class TestResolveAuthor:
    def test_cli_wins(self) -> None:
        assert _resolve_author("a@x.com", "b@x.com") == "a@x.com"

    def test_empty_cli_means_all(self) -> None:
        assert _resolve_author("", "b@x.com") is None

    def test_config_used(self) -> None:
        assert _resolve_author(None, "b@x.com") == "b@x.com"

    def test_none_when_nothing_set(self) -> None:
        assert _resolve_author(None, None) is None


# ---------------------------------------------------------------------------
# _parse_date_bound
# ---------------------------------------------------------------------------

class TestParseDateBound:
    def test_iso_date(self) -> None:
        from datetime import date
        assert _parse_date_bound("2025-03-15", 7) == date(2025, 3, 15)

    def test_n_days_ago(self) -> None:
        from datetime import date, timedelta
        assert _parse_date_bound("5 days ago", 7) == date.today() - timedelta(days=5)

    def test_yesterday(self) -> None:
        from datetime import date, timedelta
        assert _parse_date_bound("yesterday", 7) == date.today() - timedelta(days=1)

    def test_fallback_to_default(self) -> None:
        from datetime import date, timedelta
        assert _parse_date_bound("garbage", 7) == date.today() - timedelta(days=7)

    def test_none_uses_default(self) -> None:
        from datetime import date, timedelta
        assert _parse_date_bound(None, 3) == date.today() - timedelta(days=3)


# ---------------------------------------------------------------------------
# _resolve_repo_paths
# ---------------------------------------------------------------------------

def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _make_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "main"], path)
    _git(["config", "user.email", "test@example.com"], path)
    _git(["config", "user.name", "Test User"], path)
    return path


def _commit(repo: Path, message: str, name: str, content: str) -> None:
    (repo / name).write_text(content, encoding="utf-8")
    _git(["add", name], repo)
    _git(["commit", "-m", message], repo)


class TestResolveRepoPaths:
    def test_explicit_repos(self, tmp_path: Path) -> None:
        a = _make_repo(tmp_path / "a")
        b = _make_repo(tmp_path / "b")
        pairs = _resolve_repo_paths(None, f"{a},{b}")
        names = {name for _path, name in pairs}
        assert names == {"a", "b"}

    def test_single_repo_flag(self, tmp_path: Path) -> None:
        a = _make_repo(tmp_path / "a")
        pairs = _resolve_repo_paths(str(a), None)
        assert len(pairs) == 1

    def test_repos_rejects_non_git_dir(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        with pytest.raises(Exception):
            _resolve_repo_paths(None, str(plain))


# ---------------------------------------------------------------------------
# Multi-project diff scoping (regression test)
# ---------------------------------------------------------------------------

@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_config_path", lambda: tmp_path / "no-config.toml")


class TestMultiProjectDiffScoping:
    def test_diffs_requested_only_from_owning_repo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_config: None
    ) -> None:
        alpha = _make_repo(tmp_path / "alpha")
        _commit(alpha, "feat: alpha one", "a1.py", "print(1)\n")
        _commit(alpha, "wip", "a2.py", "print(2)\n")  # vague → diff collected in 'both'
        beta = _make_repo(tmp_path / "beta")
        _commit(beta, "feat: beta one", "b1.py", "print(1)\n")
        _commit(beta, "fix", "b2.py", "print(2)\n")  # vague

        alpha_hashes = {c.hash for c in get_commits(alpha)}
        beta_hashes = {c.hash for c in get_commits(beta)}

        calls: list[tuple[str, str]] = []

        def _recording_diff(repo_path, commit_hash, *args, **kwargs):
            name = Path(repo_path).name if repo_path else "<cwd>"
            calls.append((name, commit_hash))
            return "diff --git a/x b/x\n+changed\n"

        monkeypatch.setattr(cli, "get_commit_diff", _recording_diff)

        result = runner.invoke(
            app,
            [
                "standup", "--repos", f"{alpha},{beta}",
                "--context", "diffs", "--no-llm", "--json",
                "--skip-setup", "--since", "1 year ago",
            ],
        )
        assert result.exit_code == 0, result.stdout

        # Every diff fetched for an alpha commit must have queried the alpha repo
        # (and likewise for beta). The pre-fix code queried every repo for every
        # task's commits, producing cross-repo lookups.
        assert calls, "expected some diffs to be collected"
        for repo_name, h in calls:
            if h in alpha_hashes:
                assert repo_name == "alpha"
            elif h in beta_hashes:
                assert repo_name == "beta"
            else:
                pytest.fail(f"diff requested for unknown hash {h}")
        assert any(h in alpha_hashes for _n, h in calls)
        assert any(h in beta_hashes for _n, h in calls)


# ---------------------------------------------------------------------------
# changelog command (integration)
# ---------------------------------------------------------------------------

class TestChangelogCommand:
    def test_changelog_json(self, tmp_path: Path, isolated_config: None) -> None:
        repo = _make_repo(tmp_path / "repo")
        _commit(repo, "feat: add thing", "a.py", "x\n")
        _commit(repo, "fix: a bug", "b.py", "y\n")
        result = runner.invoke(
            app,
            ["changelog", "--repo", str(repo), "--json", "--no-llm", "--skip-setup"],
        )
        assert result.exit_code == 0, result.stdout
        import json
        data = json.loads(result.stdout)
        types = [s["type"] for s in data["sections"]]
        assert "feat" in types and "fix" in types

    def test_changelog_empty_range_exits_cleanly(
        self, tmp_path: Path, isolated_config: None
    ) -> None:
        repo = _make_repo(tmp_path / "repo")
        _commit(repo, "feat: only", "a.py", "x\n")
        _git(["tag", "v1.0.0"], repo)
        result = runner.invoke(
            app,
            ["changelog", "--repo", str(repo), "--from", "v1.0.0", "--no-llm", "--skip-setup"],
        )
        assert result.exit_code == 0
        assert "No changes found" in result.stdout
