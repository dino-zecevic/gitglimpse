"""Configuration loading and management."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

import tomli_w
from platformdirs import user_config_dir


def _config_path() -> Path:
    return Path(user_config_dir("gitglimpse")) / "config.toml"


@dataclass
class Config:
    default_mode: str = "template"          # template | local-llm | api | json
    llm_provider: str | None = None         # openai | anthropic | gemini | local
    llm_model: str | None = None
    local_llm_url: str = "http://localhost:11434/v1"
    api_keys: dict[str, str] = field(default_factory=dict)
    author_email: str | None = None
    default_since: str = "yesterday"


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
        # Skip empty dicts so the file stays clean.
        if isinstance(value, dict) and not value:
            continue
        data[f.name] = value

    path.write_text(tomli_w.dumps(data), encoding="utf-8")
