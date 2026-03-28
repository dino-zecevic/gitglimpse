"""LLM provider factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gitglimpse.config import Config
    from gitglimpse.providers.base import BaseLLMProvider


def get_provider(config: Config) -> BaseLLMProvider | None:
    """Return the configured provider, or None if no LLM is configured."""
    from gitglimpse.providers.base import BaseLLMProvider  # noqa: F401 (satisfies type checker)

    if config.default_mode == "local-llm":
        from gitglimpse.providers.local import LocalProvider
        return LocalProvider(
            base_url=config.local_llm_url,
            model=config.llm_model or "llama3.2",
        )

    if config.default_mode == "api":
        provider_name = config.llm_provider or ""
        api_key = config.api_keys.get(provider_name, "")

        if provider_name == "openai":
            from gitglimpse.providers.openai import OpenAIProvider
            return OpenAIProvider(api_key=api_key, model=config.llm_model or "gpt-4o-mini")

        if provider_name == "anthropic":
            from gitglimpse.providers.claude import ClaudeProvider
            return ClaudeProvider(api_key=api_key, model=config.llm_model or "claude-sonnet-4-20250514")

        if provider_name == "gemini":
            from gitglimpse.providers.gemini import GeminiProvider
            return GeminiProvider(api_key=api_key, model=config.llm_model or "gemini-2.5-flash")

    return None
