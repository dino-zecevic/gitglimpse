"""gitglimpse CLI — entry point for the `gg` command."""

from typing import Annotated, Optional

import typer
from rich.console import Console

app = typer.Typer(
    name="gg",
    help="Analyze git history and generate standup updates, reports, and summaries.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def standup(
    json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    no_llm: Annotated[bool, typer.Option("--no-llm", help="Skip LLM summarization.")] = False,
    local_llm: Annotated[
        Optional[str],
        typer.Option("--local-llm", help="Use a local LLM endpoint (e.g. http://localhost:11434)."),
    ] = None,
) -> None:
    """Generate a standup update from recent git commits."""
    console.print("standup coming soon")


@app.command()
def report(
    json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    no_llm: Annotated[bool, typer.Option("--no-llm", help="Skip LLM summarization.")] = False,
    local_llm: Annotated[
        Optional[str],
        typer.Option("--local-llm", help="Use a local LLM endpoint (e.g. http://localhost:11434)."),
    ] = None,
) -> None:
    """Generate a daily report from git commits."""
    console.print("report coming soon")


@app.command()
def week(
    json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    no_llm: Annotated[bool, typer.Option("--no-llm", help="Skip LLM summarization.")] = False,
    local_llm: Annotated[
        Optional[str],
        typer.Option("--local-llm", help="Use a local LLM endpoint (e.g. http://localhost:11434)."),
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
