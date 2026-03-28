"""gitglimpse CLI — entry point for the `gg` command."""

from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from gitglimpse.formatters.json import format_standup_json
from gitglimpse.formatters.markdown import format_report
from gitglimpse.formatters.template import format_standup
from gitglimpse.git import GitError, get_commits, get_current_author_email
from gitglimpse.grouping import group_commits_into_tasks

app = typer.Typer(
    name="gg",
    help="Analyze git history and generate standup updates, reports, and summaries.",
    no_args_is_help=True,
)
console = Console()


def _report_date(since: str) -> date:
    """Derive a display date from the --since value."""
    if since.lower() == "yesterday":
        return date.today() - timedelta(days=1)
    try:
        return date.fromisoformat(since)
    except ValueError:
        return date.today() - timedelta(days=1)


def _resolve_author(author: Optional[str], repo_path: Optional[Path]) -> Optional[str]:
    if author is not None:
        return author or None
    email = get_current_author_email(repo_path)
    return email or None


@app.command()
def standup(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    no_llm: Annotated[bool, typer.Option("--no-llm", help="Skip LLM summarization (default behaviour).")] = False,
    local_llm: Annotated[
        Optional[str],
        typer.Option("--local-llm", help="Local LLM endpoint (e.g. http://localhost:11434)."),
    ] = None,
    since: Annotated[str, typer.Option("--since", help="Show commits since this date or period.")] = "yesterday",
    author: Annotated[
        Optional[str],
        typer.Option("--author", help="Filter by author email. Defaults to current git user."),
    ] = None,
    repo: Annotated[
        Optional[str],
        typer.Option("--repo", help="Path to git repository. Defaults to current directory."),
    ] = None,
) -> None:
    """Generate a standup update from recent git commits."""
    repo_path = Path(repo) if repo else None

    try:
        resolved_author = _resolve_author(author, repo_path)
        commits = get_commits(repo_path=repo_path, since=since, author=resolved_author)
    except GitError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)

    tasks = group_commits_into_tasks(commits)
    report_date = _report_date(since)

    if as_json:
        print(format_standup_json(tasks, report_date))
    else:
        console.print(format_standup(tasks, report_date), markup=False, highlight=False)


@app.command()
def report(
    no_llm: Annotated[bool, typer.Option("--no-llm", help="Skip LLM summarization (default behaviour).")] = False,
    local_llm: Annotated[
        Optional[str],
        typer.Option("--local-llm", help="Local LLM endpoint (e.g. http://localhost:11434)."),
    ] = None,
    since: Annotated[str, typer.Option("--since", help="Show commits since this date or period.")] = "yesterday",
    author: Annotated[
        Optional[str],
        typer.Option("--author", help="Filter by author email. Defaults to current git user."),
    ] = None,
    repo: Annotated[
        Optional[str],
        typer.Option("--repo", help="Path to git repository. Defaults to current directory."),
    ] = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Save report to this file instead of printing."),
    ] = None,
) -> None:
    """Generate a daily Markdown report from git commits."""
    repo_path = Path(repo) if repo else None

    try:
        resolved_author = _resolve_author(author, repo_path)
        commits = get_commits(repo_path=repo_path, since=since, author=resolved_author)
    except GitError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)

    tasks = group_commits_into_tasks(commits)
    report_date = _report_date(since)
    md = format_report(tasks, report_date)

    if output:
        Path(output).write_text(md, encoding="utf-8")
        console.print(f"Report saved to [bold]{output}[/bold]")
    else:
        console.print(md, markup=False, highlight=False)


@app.command()
def week(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    no_llm: Annotated[bool, typer.Option("--no-llm", help="Skip LLM summarization.")] = False,
    local_llm: Annotated[
        Optional[str],
        typer.Option("--local-llm", help="Local LLM endpoint (e.g. http://localhost:11434)."),
    ] = None,
) -> None:
    """Generate a weekly summary from git commits."""
    console.print("week coming soon")


@app.command()
def config() -> None:
    """View or edit gitglimpse configuration."""
    console.print("config coming soon")


@app.command()
def init() -> None:
    """Initialize gitglimpse for the current repository."""
    console.print("init coming soon")
