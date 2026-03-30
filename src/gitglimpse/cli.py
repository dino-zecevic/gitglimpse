"""gitglimpse CLI — entry point for the `glimpse` command."""

from datetime import date, timedelta
from importlib.resources import files as _resource_files
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from gitglimpse import __version__
from gitglimpse.config import Config, is_first_run, load_config
from gitglimpse.formatters.json import format_standup_json, format_week_json
from gitglimpse.formatters.markdown import format_report
from gitglimpse.formatters.pr import format_pr_json, format_pr_template
from gitglimpse.formatters.template import format_standup, format_week_template
from gitglimpse.git import GitError, get_branch_commits, get_commit_diff, get_commits, get_current_branch_name
from gitglimpse.grouping import filter_noise_commits, group_commits_into_tasks, is_vague_message
from gitglimpse.providers import get_provider
from gitglimpse.providers.local import LocalProvider

app = typer.Typer(
    name="glimpse",
    help="Analyze git history and generate standup updates, reports, and summaries.",
    no_args_is_help=True,
)
config_app = typer.Typer(help="View or edit gitglimpse configuration.")
app.add_typer(config_app, name="config")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"gitglimpse {__version__}")
        raise typer.Exit()


@app.callback()
def _app_callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
) -> None:
    """Analyze git history and generate standup updates, reports, and summaries."""

console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_WEEK_SINCE = "7 days ago"


def _smart_default_since() -> str:
    """Return a sensible --since default based on the day of the week.

    Monday (or first workday after weekend): "last friday"
    Tuesday–Friday: "yesterday"
    Saturday/Sunday: "last friday"
    """
    weekday = date.today().weekday()  # 0=Mon … 6=Sun
    if weekday == 0:  # Monday
        return "last friday"
    if weekday <= 4:  # Tue–Fri
        return "yesterday"
    # Saturday (5) or Sunday (6)
    return "last friday"


_DEFAULT_SINCE = _smart_default_since()


def _report_date(since: str) -> date:
    """The report date is always today — the *since* just controls the lookback."""
    return date.today()


def _resolve_author(
    cli_author: Optional[str],
    cfg_author: Optional[str],
) -> Optional[str]:
    """Priority: CLI flag > config file > None (show all commits)."""
    if cli_author is not None:
        return cli_author or None
    if cfg_author:
        return cfg_author
    return None


_SENTINEL_SINCE = "__auto__"


def _effective_since(cli_since: str, cfg_since: str) -> str:
    """Resolve the --since value.

    Priority: explicit CLI flag > config default_since > smart weekday default.
    """
    if cli_since != _SENTINEL_SINCE:
        return cli_since
    if cfg_since != "yesterday":
        # User explicitly configured a non-default value.
        return cfg_since
    return _DEFAULT_SINCE


def _parse_date_bound(value: str | None, default_days_ago: int) -> date:
    """Parse a date from a CLI string, with a fallback of N days ago."""
    today = date.today()
    if value is None:
        return today - timedelta(days=default_days_ago)
    # Try ISO format first.
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    # Handle "N days ago" patterns that git also accepts.
    if value.endswith(" days ago"):
        try:
            n = int(value.split()[0])
            return today - timedelta(days=n)
        except (ValueError, IndexError):
            pass
    if value.lower() == "yesterday":
        return today - timedelta(days=1)
    if value.lower() == "last friday":
        days_since_friday = (today.weekday() - 4) % 7 or 7
        return today - timedelta(days=days_since_friday)
    return today - timedelta(days=default_days_ago)


def _load_or_onboard(skip_setup: bool) -> Config:
    """Load config, running onboarding on first use unless skipped."""
    if skip_setup or not is_first_run():
        return load_config()

    from rich.panel import Panel
    from gitglimpse.onboarding import run_onboarding

    console.print()
    console.print(Panel(
        "Welcome to [bold]gitglimpse[/bold]! Let's set up your preferences.",
        border_style="cyan",
    ))
    cfg = run_onboarding(existing_config=None)
    console.print()
    console.rule(style="dim")
    console.print()
    return cfg


def _is_git_repo(path: Path) -> bool:
    """Return True if *path* is the root of a git repository."""
    return (path / ".git").exists()


def _discover_repos(base: Path) -> list[Path]:
    """Scan immediate subdirectories of *base* for git repos."""
    repos: list[Path] = []
    try:
        for child in sorted(base.iterdir()):
            if child.is_dir() and not child.name.startswith(".") and _is_git_repo(child):
                repos.append(child)
    except PermissionError:
        pass
    return repos


def _resolve_repo_paths(
    cli_repo: Optional[str],
    cli_repos: Optional[str],
) -> list[tuple[Path, str]]:
    """Return a list of (repo_path, project_name) tuples.

    Returns a single-element list for single-project mode or multiple
    for multi-project.  Raises typer.Exit on failure.
    """
    # Explicit --repos flag takes priority.
    if cli_repos:
        pairs: list[tuple[Path, str]] = []
        for raw in cli_repos.split(","):
            p = Path(raw.strip()).resolve()
            if not p.is_dir():
                console.print(f"[bold red]Error:[/bold red] Not a directory: {p}")
                raise typer.Exit(1)
            if not _is_git_repo(p):
                console.print(f"[bold red]Error:[/bold red] Not a git repository: {p}")
                raise typer.Exit(1)
            pairs.append((p, p.name))
        return pairs

    # Explicit --repo flag.
    if cli_repo:
        return [(Path(cli_repo).resolve(), "")]

    # Auto-detect: check cwd first.
    cwd = Path.cwd()
    if _is_git_repo(cwd):
        return [(cwd, "")]

    # cwd is not a repo → scan subdirectories.
    repos = _discover_repos(cwd)
    if not repos:
        console.print(
            "[bold red]Error:[/bold red] No git repository found. "
            "Run from a git repo or a folder containing git repos."
        )
        raise typer.Exit(1)

    names = ", ".join(r.name for r in repos)
    console.print(f"[dim]Found {len(repos)} projects: {names}[/dim]", highlight=False)
    return [(r, r.name) for r in repos]


def _collect_multi_project(
    repo_pairs: list[tuple[Path, str]],
    since: str | None,
    until: str | None,
    author: str | None,
) -> list:
    """Collect and group commits from multiple repos.

    Returns a flat list of Tasks with .project set.
    """
    all_tasks: list = []
    for repo_path, project_name in repo_pairs:
        try:
            commits = get_commits(
                repo_path=repo_path, since=since, until=until, author=author,
            )
        except GitError:
            continue
        tasks = group_commits_into_tasks(commits, project=project_name)
        all_tasks.extend(tasks)
    all_tasks.sort(key=lambda t: t.first_commit_time)
    return all_tasks


def _collect_diff_snippets(
    tasks: list,
    repo_path: Optional[Path],
    all_commits: bool = False,
) -> dict[str, str]:
    """Return a mapping of commit_hash → diff snippet.

    When *all_commits* is True, collect diffs for every commit (for --prefer-diff).
    Otherwise, only collect for commits with vague messages.
    """
    snippets: dict[str, str] = {}
    for task in tasks:
        for commit in task.commits:
            if commit.hash not in snippets and (all_commits or is_vague_message(commit.message)):
                try:
                    snippets[commit.hash] = get_commit_diff(repo_path, commit.hash)
                except GitError:
                    pass  # skip if diff can't be retrieved
    return snippets


def _print_status_line(
    resolved_author: Optional[str],
    provider: object | None,
    ctx_mode: str = "commits",
) -> None:
    """Print a one-line dim status showing author, context, and active model."""
    from gitglimpse.providers.openai import OpenAIProvider
    from gitglimpse.providers.claude import ClaudeProvider
    from gitglimpse.providers.gemini import GeminiProvider

    author_val = resolved_author or "all"
    context_val = "commits + diffs" if ctx_mode == "both" else ctx_mode

    parts = [f"Author: {author_val}", f"Context: {context_val}"]

    if provider is not None:
        if isinstance(provider, LocalProvider):
            model = getattr(provider, "model", None) or "local-llm"
        elif isinstance(provider, OpenAIProvider):
            model = f"{getattr(provider, 'model', 'unknown')} (OpenAI)"
        elif isinstance(provider, ClaudeProvider):
            model = f"{getattr(provider, 'model', 'unknown')} (Anthropic)"
        elif isinstance(provider, GeminiProvider):
            model = f"{getattr(provider, 'model', 'unknown')} (Gemini)"
        else:
            model = getattr(provider, "model", "unknown")
        parts.append(f"Model: {model}")

    console.print("[dim]" + " · ".join(parts) + "[/dim]", highlight=False)


def _resolve_provider(
    cfg: Config,
    use_local: bool,
    local_url_override: Optional[str],
    model_override: Optional[str] = None,
    context_mode: str = "commits",
) -> object | None:
    """Return the appropriate provider, or None for template-only output.

    Priority:
      1. --local-llm flag → LocalProvider (with optional URL override)
      2. config default_mode == local-llm / api → get_provider()
      3. anything else → None (template fallback)
    """
    if use_local:
        url = local_url_override or cfg.local_llm_url
        model = model_override or cfg.llm_model or None
        return LocalProvider(base_url=url, model=model, context_mode=context_mode)
    if cfg.default_mode in ("local-llm", "api"):
        if model_override:
            cfg.llm_model = model_override
        p = get_provider(cfg, context_mode=context_mode)
        return p
    return None


# ---------------------------------------------------------------------------
# standup
# ---------------------------------------------------------------------------

@app.command()
def standup(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    no_llm: Annotated[bool, typer.Option("--no-llm", help="Skip LLM, use template formatter.")] = False,
    local_llm: Annotated[bool, typer.Option("--local-llm", help="Use local LLM (Ollama).")] = False,
    local_llm_url: Annotated[
        Optional[str],
        typer.Option("--local-llm-url", help="Override local LLM base URL."),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", help="LLM model to use (e.g. qwen2.5-coder:latest)."),
    ] = None,
    since: Annotated[str, typer.Option("--since", help="Show commits since this date or period.")] = _SENTINEL_SINCE,
    author: Annotated[
        Optional[str],
        typer.Option("--author", help="Filter by author email."),
    ] = None,
    repo: Annotated[
        Optional[str],
        typer.Option("--repo", help="Path to git repository. Defaults to current directory."),
    ] = None,
    repos: Annotated[
        Optional[str],
        typer.Option("--repos", help="Comma-separated list of repo paths for multi-project mode."),
    ] = None,
    context: Annotated[
        Optional[str],
        typer.Option("--context", help="LLM context: 'commits', 'diffs', or 'both'."),
    ] = None,
    group: Annotated[
        Optional[str],
        typer.Option("--group", help="Multi-project grouping: 'project' (default) or 'task' (flat list)."),
    ] = None,
    filter_noise: Annotated[
        Optional[bool],
        typer.Option("--filter-noise/--no-filter-noise", help="Filter out noise commits (merges, formatting, lock files)."),
    ] = None,
    skip_setup: Annotated[
        bool,
        typer.Option("--skip-setup", help="Skip first-run onboarding.", hidden=True),
    ] = False,
) -> None:
    """Generate a standup update from recent git commits.

    \b
    Examples:
      glimpse standup
      glimpse standup --since "2 days ago"
      glimpse standup --json
      glimpse standup --context diffs
      glimpse standup --repos "api,frontend,landing"
    """
    cfg = _load_or_onboard(skip_setup)
    effective = _effective_since(since, cfg.default_since)
    ctx_mode = context or cfg.context_mode
    resolved_author = _resolve_author(author, cfg.author_email)
    group_by = group or cfg.group_by
    do_filter = filter_noise if filter_noise is not None else cfg.filter_noise

    repo_pairs = _resolve_repo_paths(repo, repos)
    multi = len(repo_pairs) > 1

    filtered_count = 0
    if multi:
        tasks = _collect_multi_project(repo_pairs, effective, None, resolved_author)
    else:
        repo_path = repo_pairs[0][0] if repo_pairs[0][1] else (Path(repo) if repo else None)
        try:
            commits = get_commits(repo_path=repo_path, since=effective, author=resolved_author)
        except GitError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(1)
        if do_filter:
            original_count = len(commits)
            commits = filter_noise_commits(commits)
            filtered_count = original_count - len(commits)
        tasks = group_commits_into_tasks(commits)

    report_date = _report_date(effective)

    diff_snippets: dict[str, str] | None = None
    if ctx_mode in ("diffs", "both"):
        if multi:
            diff_snippets = {}
            for rp, _ in repo_pairs:
                diff_snippets.update(
                    _collect_diff_snippets(tasks, rp, all_commits=True)
                )
        else:
            rp = repo_pairs[0][0] if repo_pairs[0][1] else (Path(repo) if repo else None)
            diff_snippets = _collect_diff_snippets(tasks, rp, all_commits=True)

    if as_json:
        since_date = _parse_date_bound(effective, 1)
        json_str = format_standup_json(tasks, report_date, since_date, diff_snippets=diff_snippets, context_mode=ctx_mode)
        if filtered_count > 0:
            import json as _json
            data = _json.loads(json_str)
            data["filtered_commits"] = filtered_count
            json_str = _json.dumps(data, indent=2)
        print(json_str)
        return

    if filtered_count > 0:
        console.print(f"[dim]Filtered {filtered_count} noise commits (merges, formatting, dependencies)[/dim]", highlight=False)

    active_provider: object | None = None
    llm_output: str | None = None
    if not no_llm:
        provider = _resolve_provider(cfg, local_llm, local_llm_url, model, context_mode=ctx_mode)
        if provider is not None:
            if isinstance(provider, LocalProvider) and not provider.is_available():
                if local_llm:
                    console.print(
                        "[yellow]⚠ Local LLM not reachable — falling back to template.[/yellow]"
                    )
            else:
                active_provider = provider
                llm_output = provider.summarize_standup(tasks, report_date, diff_snippets)

    _print_status_line(resolved_author, active_provider, ctx_mode)
    if llm_output:
        console.print(llm_output, markup=False, highlight=False)
    else:
        console.print(
            format_standup(tasks, report_date, group_by=group_by if multi else "project"),
            highlight=False,
        )


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@app.command()
def report(
    no_llm: Annotated[bool, typer.Option("--no-llm", help="Skip LLM, use Markdown formatter.")] = False,
    local_llm: Annotated[bool, typer.Option("--local-llm", help="Use local LLM (Ollama).")] = False,
    local_llm_url: Annotated[
        Optional[str],
        typer.Option("--local-llm-url", help="Override local LLM base URL."),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", help="LLM model to use (e.g. qwen2.5-coder:latest)."),
    ] = None,
    since: Annotated[str, typer.Option("--since", help="Show commits since this date or period.")] = _SENTINEL_SINCE,
    author: Annotated[
        Optional[str],
        typer.Option("--author", help="Filter by author email."),
    ] = None,
    repo: Annotated[
        Optional[str],
        typer.Option("--repo", help="Path to git repository. Defaults to current directory."),
    ] = None,
    repos: Annotated[
        Optional[str],
        typer.Option("--repos", help="Comma-separated list of repo paths for multi-project mode."),
    ] = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Save report to this file instead of printing."),
    ] = None,
    context: Annotated[
        Optional[str],
        typer.Option("--context", help="LLM context: 'commits', 'diffs', or 'both'."),
    ] = None,
    filter_noise: Annotated[
        Optional[bool],
        typer.Option("--filter-noise/--no-filter-noise", help="Filter out noise commits (merges, formatting, lock files)."),
    ] = None,
    skip_setup: Annotated[
        bool,
        typer.Option("--skip-setup", help="Skip first-run onboarding.", hidden=True),
    ] = False,
) -> None:
    """Generate a daily Markdown report from git commits.

    \b
    Examples:
      glimpse report
      glimpse report -o daily.md
      glimpse report --since 2025-03-01
    """
    cfg = _load_or_onboard(skip_setup)
    effective = _effective_since(since, cfg.default_since)
    ctx_mode = context or cfg.context_mode
    resolved_author = _resolve_author(author, cfg.author_email)
    do_filter = filter_noise if filter_noise is not None else cfg.filter_noise

    repo_pairs = _resolve_repo_paths(repo, repos)
    multi = len(repo_pairs) > 1

    filtered_count = 0
    if multi:
        tasks = _collect_multi_project(repo_pairs, effective, None, resolved_author)
    else:
        repo_path = repo_pairs[0][0] if repo_pairs[0][1] else (Path(repo) if repo else None)
        try:
            commits = get_commits(repo_path=repo_path, since=effective, author=resolved_author)
        except GitError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(1)
        if do_filter:
            original_count = len(commits)
            commits = filter_noise_commits(commits)
            filtered_count = original_count - len(commits)
        tasks = group_commits_into_tasks(commits)

    report_date = _report_date(effective)

    if filtered_count > 0:
        console.print(f"[dim]Filtered {filtered_count} noise commits (merges, formatting, dependencies)[/dim]", highlight=False)

    active_provider: object | None = None
    llm_output: str | None = None
    if not no_llm:
        provider = _resolve_provider(cfg, local_llm, local_llm_url, model, context_mode=ctx_mode)
        if provider is not None:
            if isinstance(provider, LocalProvider) and not provider.is_available():
                if local_llm:
                    console.print(
                        "[yellow]⚠ Local LLM not reachable — falling back to Markdown formatter.[/yellow]"
                    )
            else:
                diff_snippets = _collect_diff_snippets(tasks, None, all_commits=True) if ctx_mode in ("diffs", "both") else None
                active_provider = provider
                llm_output = provider.summarize_report(tasks, report_date, diff_snippets)

    md = llm_output if llm_output else format_report(tasks, report_date)

    _print_status_line(resolved_author, active_provider, ctx_mode)
    if output:
        Path(output).write_text(md, encoding="utf-8")
        console.print(f"Report saved to [bold]{output}[/bold]")
    else:
        console.print(md, markup=False, highlight=False)


# ---------------------------------------------------------------------------
# week (stub)
# ---------------------------------------------------------------------------

@app.command()
def week(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    no_llm: Annotated[bool, typer.Option("--no-llm", help="Skip LLM, use template formatter.")] = False,
    local_llm: Annotated[bool, typer.Option("--local-llm", help="Use local LLM (Ollama).")] = False,
    local_llm_url: Annotated[
        Optional[str],
        typer.Option("--local-llm-url", help="Override local LLM base URL."),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", help="LLM model to use (e.g. qwen2.5-coder:latest)."),
    ] = None,
    since: Annotated[
        str,
        typer.Option("--since", help="Start of week range (default: 7 days ago)."),
    ] = _DEFAULT_WEEK_SINCE,
    until: Annotated[
        Optional[str],
        typer.Option("--until", help="End of week range (default: today)."),
    ] = None,
    author: Annotated[
        Optional[str],
        typer.Option("--author", help="Filter by author email."),
    ] = None,
    repo: Annotated[
        Optional[str],
        typer.Option("--repo", help="Path to git repository. Defaults to current directory."),
    ] = None,
    repos: Annotated[
        Optional[str],
        typer.Option("--repos", help="Comma-separated list of repo paths for multi-project mode."),
    ] = None,
    context: Annotated[
        Optional[str],
        typer.Option("--context", help="LLM context: 'commits', 'diffs', or 'both'."),
    ] = None,
    filter_noise: Annotated[
        Optional[bool],
        typer.Option("--filter-noise/--no-filter-noise", help="Filter out noise commits (merges, formatting, lock files)."),
    ] = None,
    skip_setup: Annotated[
        bool,
        typer.Option("--skip-setup", help="Skip first-run onboarding.", hidden=True),
    ] = False,
) -> None:
    """Generate a weekly summary from git commits.

    \b
    Examples:
      glimpse week
      glimpse week --since "14 days ago" --until "7 days ago"
      glimpse week --json
    """
    cfg = _load_or_onboard(skip_setup)
    ctx_mode = context or cfg.context_mode
    resolved_author = _resolve_author(author, cfg.author_email)
    do_filter = filter_noise if filter_noise is not None else cfg.filter_noise

    repo_pairs = _resolve_repo_paths(repo, repos)
    multi = len(repo_pairs) > 1

    filtered_count = 0
    if multi:
        tasks = _collect_multi_project(repo_pairs, since, until, resolved_author)
    else:
        repo_path = repo_pairs[0][0] if repo_pairs[0][1] else (Path(repo) if repo else None)
        try:
            commits = get_commits(
                repo_path=repo_path,
                since=since,
                until=until,
                author=resolved_author,
            )
        except GitError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(1)
        if do_filter:
            original_count = len(commits)
            commits = filter_noise_commits(commits)
            filtered_count = original_count - len(commits)
        tasks = group_commits_into_tasks(commits)

    start_date = _parse_date_bound(since, 7)
    end_date = _parse_date_bound(until, 0)  # 0 days ago = today

    diff_snippets = _collect_diff_snippets(tasks, None, all_commits=True) if ctx_mode in ("diffs", "both") else None

    if as_json:
        json_str = format_week_json(tasks, start_date, end_date, diff_snippets=diff_snippets, context_mode=ctx_mode)
        if filtered_count > 0:
            import json as _json
            data = _json.loads(json_str)
            data["filtered_commits"] = filtered_count
            json_str = _json.dumps(data, indent=2)
        print(json_str)
        return

    if filtered_count > 0:
        console.print(f"[dim]Filtered {filtered_count} noise commits (merges, formatting, dependencies)[/dim]", highlight=False)

    active_provider: object | None = None
    llm_output: str | None = None
    if not no_llm:
        provider = _resolve_provider(cfg, local_llm, local_llm_url, model, context_mode=ctx_mode)
        if provider is not None:
            if isinstance(provider, LocalProvider) and not provider.is_available():
                if local_llm:
                    console.print(
                        "[yellow]⚠ Local LLM not reachable — falling back to template.[/yellow]"
                    )
            else:
                active_provider = provider
                llm_output = provider.summarize_week(tasks, start_date, end_date, diff_snippets)

    _print_status_line(resolved_author, active_provider, ctx_mode)
    if llm_output:
        console.print(llm_output, markup=False, highlight=False)
    else:
        console.print(
            format_week_template(tasks, start_date, end_date),
            highlight=False,
        )


# ---------------------------------------------------------------------------
# pr
# ---------------------------------------------------------------------------

@app.command()
def pr(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    no_llm: Annotated[bool, typer.Option("--no-llm", help="Skip LLM, use template formatter.")] = False,
    local_llm: Annotated[bool, typer.Option("--local-llm", help="Use local LLM (Ollama).")] = False,
    local_llm_url: Annotated[
        Optional[str],
        typer.Option("--local-llm-url", help="Override local LLM base URL."),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", help="LLM model to use (e.g. qwen2.5-coder:latest)."),
    ] = None,
    base: Annotated[
        str,
        typer.Option("--base", help="Base branch to compare against."),
    ] = "main",
    repo: Annotated[
        Optional[str],
        typer.Option("--repo", help="Path to git repository. Defaults to current directory."),
    ] = None,
    context: Annotated[
        Optional[str],
        typer.Option("--context", help="LLM context: 'commits', 'diffs', or 'both'."),
    ] = None,
    filter_noise: Annotated[
        Optional[bool],
        typer.Option("--filter-noise/--no-filter-noise", help="Filter out noise commits (merges, formatting, lock files)."),
    ] = None,
    skip_setup: Annotated[
        bool,
        typer.Option("--skip-setup", help="Skip first-run onboarding.", hidden=True),
    ] = False,
) -> None:
    """Generate a pull request summary. Best results with --local-llm or a configured API provider.

    \b
    Examples:
      glimpse pr
      glimpse pr --base main
      glimpse pr --json
      glimpse pr --context diffs
    """
    cfg = _load_or_onboard(skip_setup)
    # PR defaults to "both" context for richer output, unless explicitly overridden.
    ctx_mode = context or "both"
    do_filter = filter_noise if filter_noise is not None else cfg.filter_noise

    repo_path = Path(repo).resolve() if repo else None

    # Get current branch name.
    try:
        current_branch = get_current_branch_name(repo_path)
    except GitError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)

    # Get commits on this branch that aren't on base.
    try:
        commits = get_branch_commits(repo_path=repo_path, base=base)
    except GitError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)

    if not commits:
        console.print(f"No commits on this branch compared to [bold]{base}[/bold].")
        raise typer.Exit(0)

    # Noise filtering.
    filtered_count = 0
    if do_filter:
        original_count = len(commits)
        commits = filter_noise_commits(commits)
        filtered_count = original_count - len(commits)

    tasks = group_commits_into_tasks(commits)

    # Extract ticket from branch.
    from gitglimpse.grouping import extract_ticket_id
    ticket = extract_ticket_id(current_branch)

    # Collect diff snippets if needed.
    diff_snippets: dict[str, str] | None = None
    if ctx_mode in ("diffs", "both"):
        diff_snippets = _collect_diff_snippets(tasks, repo_path, all_commits=True)

    # JSON output.
    if as_json:
        print(format_pr_json(
            tasks, current_branch, base,
            ticket=ticket,
            filtered_count=filtered_count,
            diff_snippets=diff_snippets,
            context_mode=ctx_mode,
        ))
        return

    if filtered_count > 0:
        console.print(f"[dim]Filtered {filtered_count} noise commits (merges, formatting, dependencies)[/dim]", highlight=False)

    # LLM output.
    active_provider: object | None = None
    llm_output: str | None = None
    if not no_llm:
        provider = _resolve_provider(cfg, local_llm, local_llm_url, model, context_mode=ctx_mode)
        if provider is not None:
            if isinstance(provider, LocalProvider) and not provider.is_available():
                if local_llm:
                    console.print(
                        "[yellow]⚠ Local LLM not reachable — falling back to template.[/yellow]"
                    )
            else:
                active_provider = provider
                llm_output = provider.summarize_pr(tasks, current_branch, base, diff_snippets)

    _print_status_line(None, active_provider, ctx_mode)
    if llm_output:
        console.print(llm_output, markup=False, highlight=False)
    else:
        console.print(
            format_pr_template(tasks, current_branch, base, ticket=ticket),
            highlight=False,
        )
        # Show tip if no LLM is configured at all (not just unavailable this run).
        if active_provider is None and cfg.default_mode == "template":
            console.print()
            console.print(
                "[dim]Tip: PR summaries are richer with an LLM. "
                "Try: glimpse pr --local-llm[/dim]",
                highlight=False,
            )


# ---------------------------------------------------------------------------
# config show
# ---------------------------------------------------------------------------

@config_app.command("show")
def config_show() -> None:
    """Display the current configuration."""
    cfg = load_config()

    table = Table(title="gitglimpse config", show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="bold")
    table.add_column("Value")

    table.add_row("default_mode", cfg.default_mode)
    table.add_row("default_since", cfg.default_since)
    table.add_row("author_email", cfg.author_email or "[dim](not set)[/dim]")
    table.add_row("llm_provider", cfg.llm_provider or "[dim](not set)[/dim]")
    table.add_row("llm_model", cfg.llm_model or "[dim](not set)[/dim]")
    table.add_row("local_llm_url", cfg.local_llm_url)
    table.add_row("api_key_env", cfg.api_key_env or "[dim](not set)[/dim]")
    table.add_row("context_mode", cfg.context_mode)
    table.add_row("group_by", cfg.group_by)

    console.print(table)


# ---------------------------------------------------------------------------
# config setup
# ---------------------------------------------------------------------------

@config_app.command("setup")
def config_setup() -> None:
    """Interactive setup: choose LLM mode and configure credentials."""
    from gitglimpse.onboarding import run_onboarding

    cfg = load_config()
    run_onboarding(existing_config=cfg)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

_COMMAND_TEMPLATES = ("standup.md", "report.md", "week.md", "pr.md")


def _read_template(name: str) -> str:
    return (
        _resource_files("gitglimpse.commands")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )


def _write_command_file(
    dest: Path,
    content: str,
    force: bool,
    dry_run: bool,
) -> bool:
    """Write *dest* with *content*. Return True if the file was written."""
    if dest.exists() and not force:
        overwrite = typer.confirm(f"  {dest} already exists. Overwrite?", default=False)
        if not overwrite:
            console.print(f"  [dim]Skipped {dest}[/dim]")
            return False
    if not dry_run:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return True


@app.command()
def init(
    cursor: Annotated[
        bool,
        typer.Option("--cursor", help="Also create .cursor/commands/ files."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing files without prompting."),
    ] = False,
    repo: Annotated[
        Optional[str],
        typer.Option("--repo", help="Target repository root. Defaults to current directory."),
    ] = None,
) -> None:
    """Initialize Claude Code (and optionally Cursor) slash-command files.

    \b
    Examples:
      glimpse init
      glimpse init --cursor
      glimpse init --force
    """
    root = Path(repo) if repo else Path.cwd()

    try:
        cfg = load_config()
        context_mode = cfg.context_mode
    except Exception:
        context_mode = "commits"

    targets: list[tuple[Path, str]] = [
        (root / ".claude" / "commands", "Claude Code"),
    ]
    if cursor:
        targets.append((root / ".cursor" / "commands", "Cursor"))

    created: list[Path] = []
    skipped: list[Path] = []

    console.print(f"[dim]Context mode: {context_mode}  (change with: glimpse config setup)[/dim]")

    for commands_dir, tool_name in targets:
        console.print(f"\n[bold]{tool_name}[/bold] → {commands_dir}")
        for name in _COMMAND_TEMPLATES:
            dest = commands_dir / name
            try:
                content = _read_template(name)
            except Exception as exc:
                console.print(f"  [red]Could not read template {name}: {exc}[/red]")
                continue
            content = content.replace(
                "glimpse standup --json",
                f"glimpse standup --json --context {context_mode}",
            ).replace(
                "glimpse week --json",
                f"glimpse week --json --context {context_mode}",
            ).replace(
                "glimpse pr --json",
                f"glimpse pr --json --context {context_mode}",
            )
            written = _write_command_file(dest, content, force=force, dry_run=False)
            if written:
                console.print(f"  [green]✓[/green] Created {dest.relative_to(root)}")
                created.append(dest)
            else:
                skipped.append(dest)

    console.print()
    if created:
        console.print(
            f"[bold green]Done.[/bold green] "
            f"Created {len(created)} file{'s' if len(created) != 1 else ''}."
        )
    else:
        console.print("[yellow]No files were created.[/yellow]")
