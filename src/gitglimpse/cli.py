"""gitglimpse CLI — entry point for the `glimpse` command."""

from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from gitglimpse.config import Config, load_config, save_config
from gitglimpse.formatters.json import format_standup_json, format_week_json
from gitglimpse.formatters.markdown import format_report
from gitglimpse.formatters.template import format_standup, format_week_template
from gitglimpse.git import GitError, get_commits, get_current_author_email
from gitglimpse.grouping import group_commits_into_tasks
from gitglimpse.providers import get_provider
from gitglimpse.providers.local import LocalProvider

app = typer.Typer(
    name="glimpse",
    help="Analyze git history and generate standup updates, reports, and summaries.",
    no_args_is_help=True,
)
config_app = typer.Typer(help="View or edit gitglimpse configuration.")
app.add_typer(config_app, name="config")

console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_SINCE = "yesterday"
_DEFAULT_WEEK_SINCE = "7 days ago"

_API_KEY_PREFIXES: dict[str, str] = {
    "openai": "sk-",
    "anthropic": "sk-ant-",
    "gemini": "AIza",
}


def _report_date(since: str) -> date:
    if since.lower() == "yesterday":
        return date.today() - timedelta(days=1)
    try:
        return date.fromisoformat(since)
    except ValueError:
        return date.today() - timedelta(days=1)


def _resolve_author(
    cli_author: Optional[str],
    cfg_author: Optional[str],
    repo_path: Optional[Path],
) -> Optional[str]:
    """Priority: CLI flag > config file > git config user.email."""
    if cli_author is not None:
        return cli_author or None
    if cfg_author:
        return cfg_author
    email = get_current_author_email(repo_path)
    return email or None


def _effective_since(cli_since: str, cfg_since: str) -> str:
    """Use the config default only when the CLI flag is still at its default."""
    return cfg_since if cli_since == _DEFAULT_SINCE else cli_since


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
    return today - timedelta(days=default_days_ago)


def _mask_key(key: str) -> str:
    if len(key) <= 4:
        return "****"
    return f"****{key[-4:]}"


def _resolve_provider(
    cfg: Config,
    use_local: bool,
    local_url_override: Optional[str],
) -> object | None:
    """Return the appropriate provider, or None for template-only output.

    Priority:
      1. --local-llm flag → LocalProvider (with optional URL override)
      2. config default_mode == local-llm / api → get_provider()
      3. anything else → None (template fallback)
    """
    if use_local:
        url = local_url_override or cfg.local_llm_url
        model = cfg.llm_model or "llama3.2"
        return LocalProvider(base_url=url, model=model)
    if cfg.default_mode in ("local-llm", "api"):
        p = get_provider(cfg)
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
    since: Annotated[str, typer.Option("--since", help="Show commits since this date or period.")] = _DEFAULT_SINCE,
    author: Annotated[
        Optional[str],
        typer.Option("--author", help="Filter by author email. Defaults to saved config or git user."),
    ] = None,
    repo: Annotated[
        Optional[str],
        typer.Option("--repo", help="Path to git repository. Defaults to current directory."),
    ] = None,
) -> None:
    """Generate a standup update from recent git commits."""
    cfg = load_config()
    repo_path = Path(repo) if repo else None
    effective = _effective_since(since, cfg.default_since)

    try:
        resolved_author = _resolve_author(author, cfg.author_email, repo_path)
        commits = get_commits(repo_path=repo_path, since=effective, author=resolved_author)
    except GitError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)

    tasks = group_commits_into_tasks(commits)
    report_date = _report_date(effective)

    if as_json:
        print(format_standup_json(tasks, report_date))
        return

    llm_output: str | None = None
    if not no_llm:
        provider = _resolve_provider(cfg, local_llm, local_llm_url)
        if provider is not None:
            if isinstance(provider, LocalProvider) and not provider.is_available():
                console.print(
                    "[yellow]⚠ Local LLM not reachable — falling back to template.[/yellow]"
                )
            else:
                llm_output = provider.summarize_standup(tasks, report_date)

    console.print(
        llm_output if llm_output else format_standup(tasks, report_date),
        markup=False,
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
    since: Annotated[str, typer.Option("--since", help="Show commits since this date or period.")] = _DEFAULT_SINCE,
    author: Annotated[
        Optional[str],
        typer.Option("--author", help="Filter by author email. Defaults to saved config or git user."),
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
    cfg = load_config()
    repo_path = Path(repo) if repo else None
    effective = _effective_since(since, cfg.default_since)

    try:
        resolved_author = _resolve_author(author, cfg.author_email, repo_path)
        commits = get_commits(repo_path=repo_path, since=effective, author=resolved_author)
    except GitError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)

    tasks = group_commits_into_tasks(commits)
    report_date = _report_date(effective)

    llm_output: str | None = None
    if not no_llm:
        provider = _resolve_provider(cfg, local_llm, local_llm_url)
        if provider is not None:
            if isinstance(provider, LocalProvider) and not provider.is_available():
                console.print(
                    "[yellow]⚠ Local LLM not reachable — falling back to Markdown formatter.[/yellow]"
                )
            else:
                llm_output = provider.summarize_report(tasks, report_date)

    md = llm_output if llm_output else format_report(tasks, report_date)

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
        typer.Option("--author", help="Filter by author email. Defaults to saved config or git user."),
    ] = None,
    repo: Annotated[
        Optional[str],
        typer.Option("--repo", help="Path to git repository. Defaults to current directory."),
    ] = None,
) -> None:
    """Generate a weekly summary from git commits."""
    cfg = load_config()
    repo_path = Path(repo) if repo else None

    try:
        resolved_author = _resolve_author(author, cfg.author_email, repo_path)
        commits = get_commits(
            repo_path=repo_path,
            since=since,
            until=until,
            author=resolved_author,
        )
    except GitError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)

    tasks = group_commits_into_tasks(commits)
    start_date = _parse_date_bound(since, 7)
    end_date = _parse_date_bound(until, 0)  # 0 days ago = today

    if as_json:
        print(format_week_json(tasks, start_date, end_date))
        return

    llm_output: str | None = None
    if not no_llm:
        provider = _resolve_provider(cfg, local_llm, local_llm_url)
        if provider is not None:
            if isinstance(provider, LocalProvider) and not provider.is_available():
                console.print(
                    "[yellow]⚠ Local LLM not reachable — falling back to template.[/yellow]"
                )
            else:
                llm_output = provider.summarize_week(tasks, start_date, end_date)

    console.print(
        llm_output if llm_output else format_week_template(tasks, start_date, end_date),
        markup=False,
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

    if cfg.api_keys:
        for provider, key in cfg.api_keys.items():
            table.add_row(f"api_keys.{provider}", _mask_key(key))
    else:
        table.add_row("api_keys", "[dim](none)[/dim]")

    console.print(table)


# ---------------------------------------------------------------------------
# config setup
# ---------------------------------------------------------------------------

@config_app.command("setup")
def config_setup() -> None:
    """Interactive setup: choose LLM mode and configure credentials."""
    cfg = load_config()

    console.print("\n[bold cyan]gitglimpse setup[/bold cyan]\n")
    console.print("Choose default output mode:")
    console.print("  [bold]1[/bold]  Template  (no LLM — fast, offline)")
    console.print("  [bold]2[/bold]  Local LLM (Ollama or compatible)")
    console.print("  [bold]3[/bold]  API key   (OpenAI / Anthropic / Gemini)")
    console.print("  [bold]4[/bold]  JSON only")

    choice = typer.prompt("\nEnter choice", default="1").strip()

    if choice == "1":
        cfg.default_mode = "template"
        save_config(cfg)
        console.print("[green]✓[/green] Saved: default_mode = template")

    elif choice == "2":
        cfg.default_mode = "local-llm"
        cfg.llm_provider = "local"
        url = typer.prompt("Local LLM URL", default=cfg.local_llm_url).strip()
        cfg.local_llm_url = url

        # Test connectivity — warn but never fail.
        console.print(f"  Testing connection to {url} …", end=" ")
        try:
            import httpx  # optional dependency
            resp = httpx.get(f"{url.rstrip('/')}/models", timeout=3)
            if resp.is_success:
                console.print("[green]reachable[/green]")
            else:
                console.print(f"[yellow]responded with HTTP {resp.status_code}[/yellow]")
        except Exception as exc:
            console.print(f"[yellow]not reachable ({exc.__class__.__name__})[/yellow]")
            console.print(
                "  [dim]This is just a warning — config will be saved anyway.[/dim]"
            )

        save_config(cfg)
        console.print("[green]✓[/green] Saved: default_mode = local-llm")

    elif choice == "3":
        cfg.default_mode = "api"

        console.print("\nChoose LLM provider:")
        console.print("  [bold]1[/bold]  OpenAI")
        console.print("  [bold]2[/bold]  Anthropic")
        console.print("  [bold]3[/bold]  Gemini")

        provider_choice = typer.prompt("Enter choice", default="1").strip()
        provider_map = {"1": "openai", "2": "anthropic", "3": "gemini"}
        provider = provider_map.get(provider_choice, "openai")
        cfg.llm_provider = provider

        key = typer.prompt(f"API key for {provider}", hide_input=True).strip()
        if not key:
            console.print("[yellow]⚠ No key entered — config saved without API key.[/yellow]")
        else:
            expected_prefix = _API_KEY_PREFIXES.get(provider, "")
            if expected_prefix and not key.startswith(expected_prefix):
                console.print(
                    f"[yellow]⚠ Expected key starting with '{expected_prefix}' "
                    f"for {provider}. Double-check if this is correct.[/yellow]"
                )
            cfg.api_keys[provider] = key
            console.print(f"[green]✓[/green] API key saved for {provider}")

        save_config(cfg)
        console.print("[green]✓[/green] Saved: default_mode = api")

    elif choice == "4":
        cfg.default_mode = "json"
        save_config(cfg)
        console.print("[green]✓[/green] Saved: default_mode = json")

    else:
        console.print(f"[red]Unknown choice '{choice}'. No changes made.[/red]")
        raise typer.Exit(1)

    # Optionally set author email.
    console.print()
    set_author = typer.confirm(
        "Set a default author email filter?",
        default=bool(cfg.author_email),
    )
    if set_author:
        email = typer.prompt("Author email", default=cfg.author_email or "").strip()
        cfg.author_email = email or None
        save_config(cfg)
        console.print(f"[green]✓[/green] author_email = {cfg.author_email}")

    console.print("\n[bold green]Setup complete.[/bold green] Run [bold]glimpse config show[/bold] to review.\n")


# ---------------------------------------------------------------------------
# init (stub)
# ---------------------------------------------------------------------------

@app.command()
def init() -> None:
    """Initialize gitglimpse for the current repository."""
    console.print("init coming soon")
