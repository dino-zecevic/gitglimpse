"""First-run onboarding and config setup flow."""

from __future__ import annotations

import os
from pathlib import Path

from InquirerPy import inquirer
from rich.console import Console

from gitglimpse.config import Config, save_config, _config_path
from gitglimpse.git import get_current_author_email

_console = Console()

_CUSTOM_SENTINEL = "__custom__"

_DEFAULT_ENV_VARS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
    "gemini": "gemini-2.5-flash",
}

_PROVIDER_LABELS: dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic (Claude)",
    "gemini": "Google (Gemini)",
}


def _detect_shell_config() -> Path:
    """Return the path to the user's shell config file."""
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return Path.home() / ".zshrc"
    return Path.home() / ".bashrc"


def _step_identity(cfg: Config, is_reconfig: bool) -> None:
    """Step 1: Git identity / author filter."""
    _console.print("\n[bold]Step 1 — Git Identity[/bold]")

    git_email = get_current_author_email()

    choices = []
    if git_email:
        choices.append({"name": f"{git_email} (from git config)", "value": git_email})
    choices.append({"name": "All authors (show everyone's commits)", "value": None})
    choices.append({"name": "Enter a different email", "value": _CUSTOM_SENTINEL})

    # Determine default
    default: str | None = None
    if is_reconfig and cfg.author_email:
        # Pre-select the current value if it matches an option
        if cfg.author_email == git_email:
            default = git_email
        else:
            default = _CUSTOM_SENTINEL
    elif is_reconfig and cfg.author_email is None:
        default = None  # "All authors"
    elif git_email:
        default = git_email

    choice = inquirer.select(
        message="Which git identity should glimpse track?",
        choices=choices,
        default=default,
    ).execute()

    if choice == _CUSTOM_SENTINEL:
        email = inquirer.text(message="Email address:").execute().strip()
        cfg.author_email = email or None
    else:
        cfg.author_email = choice


def _step_mode(cfg: Config, is_reconfig: bool) -> None:
    """Step 2: Summary mode selection."""
    _console.print("\n[bold]Step 2 — Summary Mode[/bold]")

    choices = [
        {"name": "Template — no LLM, works offline, instant results", "value": "template"},
        {"name": "Local LLM — uses Ollama, runs on your machine", "value": "local-llm"},
        {"name": "Cloud API — uses your API key (OpenAI, Anthropic, or Gemini)", "value": "api"},
    ]
    default = cfg.default_mode if is_reconfig else "template"

    choice = inquirer.select(
        message="Summary mode:",
        choices=choices,
        default=default,
    ).execute()

    if choice == "template":
        cfg.default_mode = "template"
    elif choice == "local-llm":
        _setup_local_llm(cfg)
    elif choice == "api":
        _setup_cloud_api(cfg, is_reconfig)


def _setup_local_llm(cfg: Config) -> None:
    """Configure local LLM (Ollama)."""
    cfg.default_mode = "local-llm"
    cfg.llm_provider = "local"

    import httpx

    url = cfg.local_llm_url
    _console.print(f"  Checking Ollama at {url} ...", end=" ")

    try:
        resp = httpx.get(f"{url.rstrip('/')}/models", timeout=3.0)
        if not resp.is_success:
            raise ConnectionError()
        models = resp.json().get("data", [])
    except Exception:
        _console.print("[yellow]not found[/yellow]")
        _console.print("  Ollama not found at localhost:11434")
        _console.print("  Install from: https://ollama.com")
        _console.print("  Or start with: [bold]ollama serve[/bold]\n")

        fallback = inquirer.select(
            message="What would you like to do?",
            choices=[
                {"name": "Use Template mode for now (switch later with glimpse config setup)", "value": "template"},
                {"name": "Enter a custom LLM URL", "value": "custom"},
            ],
            default="template",
        ).execute()

        if fallback == "custom":
            custom_url = inquirer.text(
                message="LLM URL:",
                default=cfg.local_llm_url,
            ).execute().strip()
            cfg.local_llm_url = custom_url
        else:
            cfg.default_mode = "template"
            cfg.llm_provider = None
        return

    _console.print("[green]connected[/green]")

    if not models:
        _console.print("  [yellow]No models found. Pull one with: ollama pull qwen2.5-coder[/yellow]")
        return

    model_choices = [{"name": m["id"], "value": m["id"]} for m in models]
    default_model = cfg.llm_model if cfg.llm_model in [m["id"] for m in models] else models[0]["id"]

    picked = inquirer.select(
        message="Pick a model:",
        choices=model_choices,
        default=default_model,
    ).execute()

    cfg.llm_model = picked
    _console.print(f"  [green]✓[/green] Using model: {cfg.llm_model}")


def _setup_cloud_api(cfg: Config, is_reconfig: bool) -> None:
    """Configure cloud API provider."""
    cfg.default_mode = "api"

    provider_choices = [
        {"name": "OpenAI", "value": "openai"},
        {"name": "Anthropic (Claude)", "value": "anthropic"},
        {"name": "Google (Gemini)", "value": "gemini"},
    ]
    default_provider = cfg.llm_provider if is_reconfig and cfg.llm_provider in ("openai", "anthropic", "gemini") else "openai"

    provider = inquirer.select(
        message="Which provider?",
        choices=provider_choices,
        default=default_provider,
    ).execute()

    cfg.llm_provider = provider
    label = _PROVIDER_LABELS.get(provider, provider)

    # Environment variable for API key
    default_var = _DEFAULT_ENV_VARS.get(provider, f"{provider.upper()}_API_KEY")
    existing_var = cfg.api_key_env if is_reconfig and cfg.api_key_env else default_var

    var_name = inquirer.text(
        message=f"Environment variable for your {label} API key:",
        default=existing_var,
    ).execute().strip()
    cfg.api_key_env = var_name

    # Check if the variable is already set
    if os.environ.get(var_name):
        _console.print(f"  [green]✓[/green] Found {var_name} in environment")
    else:
        _console.print(f"  [dim]{var_name} is not set in the current environment.[/dim]")
        key = inquirer.secret(message=f"Paste your {label} API key:").execute().strip()
        if key:
            shell_cfg = _detect_shell_config()
            add_to_shell = inquirer.confirm(
                message=f'Add "export {var_name}=..." to {shell_cfg}?',
                default=True,
            ).execute()
            if add_to_shell:
                with open(shell_cfg, "a", encoding="utf-8") as f:
                    f.write(f'\nexport {var_name}="{key}"\n')
                _console.print(f"  [green]✓[/green] Added to {shell_cfg}")
                _console.print(f"  Run [bold]source {shell_cfg}[/bold] or restart your terminal to make it permanent.")
            else:
                _console.print("  Set it manually before using glimpse:")
                _console.print(f"    export {var_name}='your-key-here'")

            # Set for current process
            os.environ[var_name] = key

    # Model selection
    default_model = cfg.llm_model if is_reconfig and cfg.llm_model else _DEFAULT_MODELS.get(provider, "")
    model = inquirer.text(
        message="Model name:",
        default=default_model,
    ).execute().strip()
    cfg.llm_model = model or default_model


def _step_context_mode(cfg: Config, is_reconfig: bool) -> None:
    """Step 3: Output detail / context mode (shown for all users)."""
    _console.print("\n[bold]Step 3 — Output Detail[/bold]")

    choices = [
        {"name": "Commit messages only — fast, less detail", "value": "commits"},
        {"name": "Code diffs only — best when commit messages are vague", "value": "diffs"},
        {"name": "Both commits and diffs — most detail, best results with LLM or Claude Code", "value": "both"},
    ]
    default = cfg.context_mode if is_reconfig else "commits"

    cfg.context_mode = inquirer.select(
        message="How much detail should glimpse include in output?",
        choices=choices,
        default=default,
    ).execute()

    if cfg.default_mode == "template":
        _console.print("  [dim]This affects JSON output when used with Claude Code or other LLM tools.[/dim]")


def run_onboarding(existing_config: Config | None = None) -> Config:
    """Run the interactive onboarding/setup flow.

    If *existing_config* is None, this is the first run.
    If provided, it is a reconfiguration — current values are shown as defaults.
    """
    is_reconfig = existing_config is not None
    cfg = existing_config if existing_config else Config()

    if is_reconfig:
        _console.print("[bold cyan]Updating gitglimpse configuration.[/bold cyan]")
        _console.print("[dim]Arrow keys to navigate, Enter to confirm.[/dim]")

    _step_identity(cfg, is_reconfig)
    _step_mode(cfg, is_reconfig)
    _step_context_mode(cfg, is_reconfig)

    save_config(cfg)
    _console.print(f"\n[green]✓[/green] Config saved to {_config_path()}")
    if not is_reconfig:
        _console.print("[dim]Change anytime with: glimpse config setup[/dim]")

    return cfg
