"""LLM provider factory."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gitglimpse.config import Config
    from gitglimpse.providers.base import BaseLLMProvider


def _resolve_api_key(config: Config) -> str | None:
    """Read the API key from the environment variable named in config."""
    var = config.api_key_env
    if not var:
        return None
    key = os.environ.get(var)
    if not key:
        from gitglimpse.providers.base import _warn
        _warn.print(
            f"[yellow]⚠ {var} is not set. "
            f"Run: export {var}='your-key-here'[/yellow]"
        )
        return None
    return key


def get_provider(config: Config, *, context_mode: str = "commits") -> BaseLLMProvider | None:
    """Return the configured provider, or None if no LLM is configured."""
    from gitglimpse.providers.base import BaseLLMProvider  # noqa: F401 (satisfies type checker)

    if config.default_mode == "local-llm":
        from gitglimpse.providers.local import LocalProvider
        return LocalProvider(
            base_url=config.local_llm_url,
            model=config.llm_model or None,
            context_mode=context_mode,
        )

    if config.default_mode == "api":
        provider_name = config.llm_provider or ""
        api_key = _resolve_api_key(config)
        if not api_key:
            return None  # graceful fallback to template

        if provider_name == "openai":
            from gitglimpse.providers.openai import OpenAIProvider
            return OpenAIProvider(api_key=api_key, model=config.llm_model or "gpt-4o-mini", context_mode=context_mode)

        if provider_name == "anthropic":
            from gitglimpse.providers.claude import ClaudeProvider
            return ClaudeProvider(api_key=api_key, model=config.llm_model or "claude-sonnet-4-20250514", context_mode=context_mode)

        if provider_name == "gemini":
            from gitglimpse.providers.gemini import GeminiProvider
            return GeminiProvider(api_key=api_key, model=config.llm_model or "gemini-2.5-flash", context_mode=context_mode)

    return None
