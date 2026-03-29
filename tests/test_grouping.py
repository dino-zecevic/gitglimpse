"""Tests for commit grouping into logical tasks."""

from datetime import datetime, timedelta, timezone

import pytest

from gitglimpse.git import Commit, FileChange
from gitglimpse.grouping import Task, _is_vague, extract_ticket_id, filter_noise_commits, group_commits_into_tasks

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
        branches=branches or [],
        files=files or [_fc("src/main.py")],
        is_merge=is_merge,
    )


# ---------------------------------------------------------------------------
# _is_vague
# ---------------------------------------------------------------------------

class TestIsVague:
    @pytest.mark.parametrize("msg", [
        "fix", "Fix", "FIX",
        "update", "updates", "updated",
        "wip", "WIP",
        "asdf", "test", "testing",
        "changes", "stuff", "minor",
        "misc", "temp", "cleanup",
        "refactor", "done", "ok", "works",
        "ok",      # < 4 chars
        "x",       # < 4 chars
        "abc",     # < 4 chars
    ])
    def test_vague_messages(self, msg: str) -> None:
        assert _is_vague(msg) is True

    @pytest.mark.parametrize("msg", [
        "feat: add user authentication",
        "fix broken login redirect",
        "implement OAuth2 flow",
        "refactor auth middleware to use JWT",  # longer, not just the single word
        "update README with installation steps",  # more than just "update"
    ])
    def test_non_vague_messages(self, msg: str) -> None:
        assert _is_vague(msg) is False


# ---------------------------------------------------------------------------
# group_commits_into_tasks — branch grouping
# ---------------------------------------------------------------------------

class TestGroupByBranch:
    def test_single_branch_one_task(self) -> None:
        commits = [
            _commit("feat: add login", offset_hours=0, branches=["main"]),
            _commit("feat: add logout", offset_hours=1, branches=["main"]),
        ]
        tasks = group_commits_into_tasks(commits)
        assert len(tasks) == 1
        assert tasks[0].branch == "main"

    def test_two_branches_two_tasks(self) -> None:
        commits = [
            _commit("feat: new feature", offset_hours=0, branches=["feature"]),
            _commit("fix: prod hotfix", offset_hours=1, branches=["hotfix"]),
        ]
        tasks = group_commits_into_tasks(commits)
        assert len(tasks) == 2
        branches = {t.branch for t in tasks}
        assert branches == {"feature", "hotfix"}

    def test_commits_without_branch_grouped_together(self) -> None:
        commits = [
            _commit("chore: setup", offset_hours=0, branches=[]),
            _commit("chore: config", offset_hours=0.5, branches=[]),
        ]
        tasks = group_commits_into_tasks(commits)
        assert len(tasks) == 1
        assert tasks[0].branch == "main"

    def test_empty_commits_returns_empty(self) -> None:
        assert group_commits_into_tasks([]) == []


# ---------------------------------------------------------------------------
# group_commits_into_tasks — time proximity splitting
# ---------------------------------------------------------------------------

class TestTimeProximitySplit:
    def test_no_split_within_3h(self) -> None:
        commits = [
            _commit("feat: start", offset_hours=0),
            _commit("feat: middle", offset_hours=1.5),
            _commit("feat: finish", offset_hours=2.9),
        ]
        tasks = group_commits_into_tasks(commits)
        assert len(tasks) == 1

    def test_split_at_exactly_3h_gap(self) -> None:
        commits = [
            _commit("feat: morning", offset_hours=0),
            _commit("feat: afternoon", offset_hours=3.0),
        ]
        tasks = group_commits_into_tasks(commits)
        # Gap is exactly 3h; >3h triggers a split, so exactly 3h stays together.
        assert len(tasks) == 1

    def test_split_above_3h_gap(self) -> None:
        commits = [
            _commit("feat: morning", offset_hours=0),
            _commit("feat: afternoon", offset_hours=3.01),
        ]
        tasks = group_commits_into_tasks(commits)
        assert len(tasks) == 2

    def test_multiple_splits(self) -> None:
        commits = [
            _commit("feat: a", offset_hours=0),
            _commit("feat: b", offset_hours=4),   # +4h gap → split
            _commit("feat: c", offset_hours=8),   # +4h gap → split
        ]
        tasks = group_commits_into_tasks(commits)
        assert len(tasks) == 3

    def test_task_commit_count(self) -> None:
        commits = [
            _commit("feat: one", offset_hours=0),
            _commit("feat: two", offset_hours=1),
            _commit("feat: three", offset_hours=5),  # split here
        ]
        tasks = group_commits_into_tasks(commits)
        assert len(tasks) == 2
        counts = sorted(len(t.commits) for t in tasks)
        assert counts == [1, 2]


# ---------------------------------------------------------------------------
# group_commits_into_tasks — summary selection
# ---------------------------------------------------------------------------

class TestSummarySelection:
    def test_picks_non_vague_message(self) -> None:
        commits = [
            _commit("fix"),
            _commit("implement user authentication system"),
        ]
        tasks = group_commits_into_tasks(commits)
        assert tasks[0].summary == "implement user authentication system"

    def test_picks_longest_non_vague(self) -> None:
        commits = [
            _commit("add login"),
            _commit("implement OAuth2 flow with refresh tokens"),
            _commit("feat: fix typo"),
        ]
        tasks = group_commits_into_tasks(commits)
        assert tasks[0].summary == "implement OAuth2 flow with refresh tokens"

    def test_summary_from_file_paths_when_all_vague(self) -> None:
        commits = [
            _commit("wip", files=[_fc("auth/login.py"), _fc("auth/logout.py")]),
            _commit("fix", files=[_fc("api/orders.py")]),
        ]
        tasks = group_commits_into_tasks(commits)
        assert tasks[0].summary.startswith("Changes in")
        assert "auth/" in tasks[0].summary

    def test_summary_from_nested_file_uses_top_dir(self) -> None:
        commits = [
            _commit("wip", files=[_fc("src/api/users.py"), _fc("src/api/orders.py")]),
        ]
        tasks = group_commits_into_tasks(commits)
        assert "src/" in tasks[0].summary

    def test_summary_fallback_for_no_files_all_vague(self) -> None:
        # Merge-only commits: no files, vague messages.
        c = Commit(
            hash="b" * 40,
            author_email="dev@example.com",
            message="wip",
            timestamp=_ts(0),
            branches=[],
            files=[],
            is_merge=True,
        )
        tasks = group_commits_into_tasks([c])
        # Should not crash; returns some string.
        assert isinstance(tasks[0].summary, str)


# ---------------------------------------------------------------------------
# group_commits_into_tasks — totals and ordering
# ---------------------------------------------------------------------------

class TestTaskTotals:
    def test_insertions_deletions_summed(self) -> None:
        commits = [
            _commit("feat: a", files=[_fc("a.py", ins=10, dels=2)]),
            _commit("feat: b", offset_hours=1, files=[_fc("b.py", ins=5, dels=3)]),
        ]
        tasks = group_commits_into_tasks(commits)
        assert tasks[0].insertions == 15
        assert tasks[0].deletions == 5

    def test_tasks_sorted_by_first_commit_time(self) -> None:
        commits = [
            _commit("feat: later", offset_hours=5, branches=["b"]),
            _commit("feat: earlier", offset_hours=0, branches=["a"]),
        ]
        tasks = group_commits_into_tasks(commits)
        assert tasks[0].first_commit_time < tasks[1].first_commit_time

    def test_first_and_last_commit_times(self) -> None:
        commits = [
            _commit("feat: first", offset_hours=0),
            _commit("feat: second", offset_hours=1),
            _commit("feat: third", offset_hours=2),
        ]
        tasks = group_commits_into_tasks(commits)
        assert tasks[0].first_commit_time == _ts(0)
        assert tasks[0].last_commit_time == _ts(2)

    def test_estimated_minutes_is_positive(self) -> None:
        commits = [_commit("feat: something")]
        tasks = group_commits_into_tasks(commits)
        assert tasks[0].estimated_minutes > 0


# ---------------------------------------------------------------------------
# filter_noise_commits
# ---------------------------------------------------------------------------

class TestFilterNoiseCommits:
    def test_merge_commits_filtered(self) -> None:
        commits = [
            _commit("Merge branch 'feature' into main"),
            _commit("Merge pull request #42 from user/feature"),
            _commit("feat: real work"),
        ]
        result = filter_noise_commits(commits)
        assert len(result) == 1
        assert result[0].message == "feat: real work"

    def test_lock_file_only_commits_filtered(self) -> None:
        commits = [
            _commit(
                "install deps",
                files=[_fc("package-lock.json", 500, 200), _fc("yarn.lock", 100, 50)],
            ),
            _commit(
                "update go deps",
                files=[_fc("go.sum", 30, 10)],
            ),
        ]
        result = filter_noise_commits(commits)
        assert len(result) == 0

    def test_mixed_noise_and_real_files_not_filtered(self) -> None:
        commits = [
            _commit(
                "add feature and update deps",
                files=[
                    _fc("package-lock.json", 500, 200),
                    _fc("src/app.js", 20, 5),
                ],
            ),
        ]
        result = filter_noise_commits(commits)
        assert len(result) == 1

    def test_lint_format_message_commits_filtered(self) -> None:
        noise_messages = [
            "lint fix",
            "run formatter",
            "auto-format",
            "format code",
            "apply formatting",
            "prettier",
            "eslint fix",
            "lint",
            "format",
            "formatting",
            "update lock file",
            "update lockfile",
            "regenerate lock",
        ]
        for msg in noise_messages:
            commits = [_commit(msg)]
            result = filter_noise_commits(commits)
            assert len(result) == 0, f"Expected '{msg}' to be filtered"

    def test_lint_format_case_insensitive(self) -> None:
        commits = [
            _commit("Lint Fix"),
            _commit("RUN FORMATTER"),
            _commit("Auto-Format"),
        ]
        result = filter_noise_commits(commits)
        assert len(result) == 0

    def test_bump_commits_filtered(self) -> None:
        commits = [
            _commit("bump version to 1.2.3"),
            _commit("Bump dependencies"),
            _commit("bump"),
        ]
        result = filter_noise_commits(commits)
        assert len(result) == 0

    def test_minified_and_map_files_filtered(self) -> None:
        commits = [
            _commit(
                "build assets",
                files=[_fc("dist/app.min.js"), _fc("dist/app.min.css"), _fc("dist/app.js.map")],
            ),
        ]
        result = filter_noise_commits(commits)
        assert len(result) == 0

    def test_ci_workflow_only_commits_filtered(self) -> None:
        commits = [
            _commit(
                "update ci",
                files=[_fc(".github/workflows/ci.yml"), _fc(".github/workflows/deploy.yaml")],
            ),
        ]
        result = filter_noise_commits(commits)
        assert len(result) == 0

    def test_pyc_and_cache_files_filtered(self) -> None:
        commits = [
            _commit(
                "cache",
                files=[_fc("src/__pycache__/mod.cpython-311.pyc"), _fc("lib/util.pyc")],
            ),
        ]
        result = filter_noise_commits(commits)
        assert len(result) == 0

    def test_config_lint_files_filtered(self) -> None:
        commits = [
            _commit(
                "update config",
                files=[_fc(".prettierrc"), _fc(".eslintrc.json"), _fc(".editorconfig")],
            ),
        ]
        result = filter_noise_commits(commits)
        assert len(result) == 0

    def test_no_filter_noise_keeps_everything(self) -> None:
        """Simulates --no-filter-noise by simply not calling filter_noise_commits."""
        commits = [
            _commit("Merge branch 'feature' into main"),
            _commit("lint fix"),
            _commit("feat: real work"),
            _commit(
                "install deps",
                files=[_fc("package-lock.json", 500, 200)],
            ),
        ]
        # When --no-filter-noise is used, filter_noise_commits is not called.
        # All commits remain.
        assert len(commits) == 4

    def test_real_commits_not_filtered(self) -> None:
        commits = [
            _commit("feat: add user authentication"),
            _commit("fix: resolve login redirect bug"),
            _commit("refactor: simplify middleware chain"),
        ]
        result = filter_noise_commits(commits)
        assert len(result) == 3

    def test_empty_input(self) -> None:
        assert filter_noise_commits([]) == []

    def test_commit_with_no_files_not_filtered(self) -> None:
        """A commit with no files and a real message should be kept."""
        commits = [_commit("feat: initial commit", files=[])]
        result = filter_noise_commits(commits)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# extract_ticket_id
# ---------------------------------------------------------------------------

class TestExtractTicketId:
    @pytest.mark.parametrize("branch, expected", [
        ("feature/PROJ-123-auth-flow", "PROJ-123"),
        ("fix/BUG-42-login-crash", "BUG-42"),
        ("feat/AUTH-4567-oauth", "AUTH-4567"),
        ("TICKET-1-quick", "TICKET-1"),
        ("feature/AB-99", "AB-99"),
    ])
    def test_jira_style(self, branch: str, expected: str) -> None:
        assert extract_ticket_id(branch) == expected

    @pytest.mark.parametrize("branch, expected", [
        ("feat/gh-15-add-search", "#15"),
        ("fix/gh-100-bug", "#100"),
        ("feat/GH-7-feature", "#7"),
    ])
    def test_github_issue_gh_prefix(self, branch: str, expected: str) -> None:
        assert extract_ticket_id(branch) == expected

    @pytest.mark.parametrize("branch", [
        "hotfix/quick-patch",
        "main",
        "develop",
        "feat/add-new-feature",
        "fix/resolve-crash",
    ])
    def test_no_ticket(self, branch: str) -> None:
        assert extract_ticket_id(branch) is None

    def test_github_takes_priority_over_jira(self) -> None:
        # GitHub pattern is checked first so gh-N is normalised to #N.
        assert extract_ticket_id("feature/PROJ-1-gh-2") == "#2"

    def test_jira_wins_when_no_gh(self) -> None:
        assert extract_ticket_id("feature/PROJ-1-something") == "PROJ-1"

    def test_ticket_set_on_task_via_grouping(self) -> None:
        commits = [
            _commit("feat: auth flow", branches=["feature/PROJ-123-auth"]),
        ]
        tasks = group_commits_into_tasks(commits)
        assert tasks[0].ticket == "PROJ-123"

    def test_no_ticket_on_task_when_no_match(self) -> None:
        commits = [
            _commit("feat: something", branches=["main"]),
        ]
        tasks = group_commits_into_tasks(commits)
        assert tasks[0].ticket is None


# ---------------------------------------------------------------------------
# Ticket in formatter output
# ---------------------------------------------------------------------------

class TestTicketInFormatters:
    def test_ticket_in_template_output(self) -> None:
        from gitglimpse.formatters.template import format_standup
        commits = [
            _commit("Implemented auth flow", branches=["feature/PROJ-123-auth"]),
        ]
        tasks = group_commits_into_tasks(commits)
        output = format_standup(tasks, _BASE.date())
        assert "PROJ-123" in output

    def test_no_ticket_in_template_when_absent(self) -> None:
        from gitglimpse.formatters.template import format_standup
        commits = [
            _commit("Implemented auth flow", branches=["feat/auth"]),
        ]
        tasks = group_commits_into_tasks(commits)
        output = format_standup(tasks, _BASE.date())
        # Should not contain a JIRA-style ticket — just verify no stray "None".
        assert "None" not in output

    def test_ticket_in_json_output(self) -> None:
        import json
        from gitglimpse.formatters.json import format_standup_json
        commits = [
            _commit("Implemented auth flow", branches=["feature/PROJ-123-auth"]),
        ]
        tasks = group_commits_into_tasks(commits)
        data = json.loads(format_standup_json(tasks, _BASE.date()))
        task_data = data["days"][0]["tasks"][0]
        assert task_data["ticket"] == "PROJ-123"

    def test_no_ticket_null_in_json(self) -> None:
        import json
        from gitglimpse.formatters.json import format_standup_json
        commits = [
            _commit("Implemented auth flow", branches=["main"]),
        ]
        tasks = group_commits_into_tasks(commits)
        data = json.loads(format_standup_json(tasks, _BASE.date()))
        task_data = data["days"][0]["tasks"][0]
        assert task_data["ticket"] is None

    def test_ticket_in_markdown_output(self) -> None:
        from gitglimpse.formatters.markdown import format_report
        commits = [
            _commit("Implemented auth flow", branches=["feature/PROJ-123-auth"]),
        ]
        tasks = group_commits_into_tasks(commits)
        output = format_report(tasks, _BASE.date())
        assert "PROJ-123" in output

    def test_no_ticket_in_markdown_when_absent(self) -> None:
        from gitglimpse.formatters.markdown import format_report
        commits = [
            _commit("Implemented auth flow", branches=["feat/auth"]),
        ]
        tasks = group_commits_into_tasks(commits)
        output = format_report(tasks, _BASE.date())
        assert "None" not in output
