"""Configuration loading and management."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

import tomli_w


def _config_path() -> Path:
    return Path.home() / ".config" / "gitglimpse" / "config.toml"


def is_first_run() -> bool:
    """Return True if the config file does not exist yet."""
    return not _config_path().exists()


@dataclass
class Config:
    default_mode: str = "template"          # template | local-llm | api
    llm_provider: str | None = None         # openai | anthropic | gemini | local
    llm_model: str | None = None
    local_llm_url: str = "http://localhost:11434/v1"
    api_key_env: str | None = None          # env var name, e.g. OPENAI_API_KEY
    author_email: str | None = None
    default_since: str = "yesterday"
    context_mode: str = "commits"            # commits | diffs | both
    group_by: str = "project"              # project | task


def load_config() -> Config:
    """Load config from disk. Returns defaults if file is missing or unreadable."""
    path = _config_path()
    if not path.exists():
        return Config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return Config()

    cfg = Config()
    valid_fields = {f.name for f in fields(Config)}
    for key, value in data.items():
        if key in valid_fields:
            setattr(cfg, key, value)
    return cfg


def save_config(config: Config) -> None:
    """Persist config to disk, creating the directory if needed."""
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data: dict = {}
    for f in fields(config):
        value = getattr(config, f.name)
        if value is None:
            continue
        data[f.name] = value

    path.write_text(tomli_w.dumps(data), encoding="utf-8")
