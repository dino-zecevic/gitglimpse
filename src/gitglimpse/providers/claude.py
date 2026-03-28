"""Anthropic Claude provider."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import httpx

from gitglimpse.providers.base import BaseLLMProvider, _warn

if TYPE_CHECKING:
    from gitglimpse.grouping import Task

_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_TIMEOUT = httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0)
_MAX_TOKENS = 1024


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude messages provider."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self.api_key = api_key
        self.model = model

    def _chat(self, user_message: str) -> str | None:
        # Anthropic uses system as a top-level field, not inside messages.
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": _MAX_TOKENS,
            "system": self.get_system_prompt(),
            "messages": [{"role": "user", "content": user_message}],
        }
        try:
            resp = httpx.post(_API_URL, json=payload, headers=headers, timeout=_TIMEOUT)
            if resp.status_code == 401:
                _warn.print("[yellow]⚠ Claude: invalid API key.[/yellow]")
                return None
            if resp.status_code == 429:
                _warn.print("[yellow]⚠ Claude: rate limit reached.[/yellow]")
                return None
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]
        except httpx.TimeoutException:
            _warn.print("[yellow]⚠ Claude: request timed out.[/yellow]")
        except httpx.HTTPStatusError as exc:
            _warn.print(f"[yellow]⚠ Claude: HTTP {exc.response.status_code}.[/yellow]")
        except Exception as exc:
            _warn.print(f"[yellow]⚠ Claude: unexpected error — {exc}.[/yellow]")
        return None

    def summarize_standup(
        self,
        tasks: list[Task],
        report_date: date,
        diff_snippets: dict[str, str] | None = None,
    ) -> str | None:
        context = self._format_tasks_context(tasks, report_date, diff_snippets)
        return self._chat(
            f"Generate a standup update from the following commit data:\n\n{context}"
        )

    def summarize_report(
        self,
        tasks: list[Task],
        report_date: date,
        diff_snippets: dict[str, str] | None = None,
    ) -> str | None:
        context = self._format_tasks_context(tasks, report_date, diff_snippets)
        return self._chat(
            f"Generate a daily Markdown report from the following commit data:\n\n{context}"
        )

    def summarize_week(
        self,
        tasks: list[Task],
        start_date: date,
        end_date: date,
        diff_snippets: dict[str, str] | None = None,
    ) -> str | None:
        context = self._format_week_context(tasks, start_date, end_date, diff_snippets)
        return self._chat(
            "Generate a weekly summary with key themes and highlights "
            f"from the following commit data:\n\n{context}"
        )
