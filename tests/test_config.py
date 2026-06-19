"""Tests for config load/save round-tripping."""

from pathlib import Path

import pytest

import gitglimpse.config as config
from gitglimpse.config import Config, is_first_run, load_config, save_config


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "gitglimpse" / "config.toml"
    monkeypatch.setattr(config, "_config_path", lambda: path)
    return path


class TestConfig:
    def test_first_run_when_missing(self, isolated_config: Path) -> None:
        assert is_first_run() is True

    def test_load_returns_defaults_when_missing(self, isolated_config: Path) -> None:
        cfg = load_config()
        assert cfg.default_mode == "template"
        assert cfg.context_mode == "commits"
        assert cfg.filter_noise is True

    def test_save_then_load_roundtrip(self, isolated_config: Path) -> None:
        cfg = Config(
            default_mode="api",
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            api_key_env="OPENAI_API_KEY",
            author_email="me@example.com",
            context_mode="both",
            filter_noise=False,
        )
        save_config(cfg)
        assert not is_first_run()
        loaded = load_config()
        assert loaded.default_mode == "api"
        assert loaded.llm_provider == "openai"
        assert loaded.llm_model == "gpt-4o-mini"
        assert loaded.author_email == "me@example.com"
        assert loaded.context_mode == "both"
        assert loaded.filter_noise is False

    def test_none_values_omitted_from_file(self, isolated_config: Path) -> None:
        save_config(Config())
        text = isolated_config.read_text(encoding="utf-8")
        # llm_provider defaults to None → must not be serialised.
        assert "llm_provider" not in text

    def test_unknown_keys_ignored(self, isolated_config: Path) -> None:
        isolated_config.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.write_text(
            'default_mode = "api"\nbogus_key = "ignored"\n', encoding="utf-8"
        )
        cfg = load_config()
        assert cfg.default_mode == "api"
        assert not hasattr(cfg, "bogus_key")

    def test_corrupt_file_returns_defaults(self, isolated_config: Path) -> None:
        isolated_config.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.write_text("this is = = not valid toml [[[", encoding="utf-8")
        cfg = load_config()
        assert cfg.default_mode == "template"
