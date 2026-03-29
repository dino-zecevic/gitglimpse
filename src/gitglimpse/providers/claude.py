"""Anthropic Claude provider."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import httpx

from gitglimpse.providers.base import BaseLLMProvider, _warn, validate_llm_output

if TYPE_CHECKING:
    from gitglimpse.grouping import Task

_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_TIMEOUT = httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0)
_MAX_TOKENS = 1024


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude messages provider."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514", context_mode: str = "commits") -> None:
        self.api_key = api_key
        self.model = model
        self.context_mode = context_mode

    def _chat(self, user_message: str, system_prompt: str | None = None) -> str | None:
        if system_prompt is None:
            system_prompt = self.get_system_prompt()
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": _MAX_TOKENS,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }
        try:
            with _warn.status(f"[dim]Generating with {self.model}...[/dim]"):
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

    def _validated(self, result: str | None) -> str | None:
        if result is not None and not validate_llm_output(result):
            _warn.print("[dim]LLM output didn't match expected format — falling back to template.[/dim]")
            _warn.print("[dim]Tip: Smaller, instruction-following models like qwen2.5-coder work better than large general models.[/dim]")
            return None
        return result

    def _build_context(self, tasks: list[Task], report_date: date, diff_snippets: dict[str, str] | None) -> str:
        if self.context_mode == "diffs" and diff_snippets:
            return self._format_diff_only_context(tasks, report_date, diff_snippets)
        return self._format_tasks_context(tasks, report_date, diff_snippets)

    def _build_week_context(self, tasks: list[Task], start: date, end: date, diff_snippets: dict[str, str] | None) -> str:
        if self.context_mode == "diffs" and diff_snippets:
            return self._format_diff_only_week_context(tasks, start, end, diff_snippets)
        return self._format_week_context(tasks, start, end, diff_snippets)

    def summarize_standup(self, tasks: list[Task], report_date: date, diff_snippets: dict[str, str] | None = None) -> str | None:
        context = self._build_context(tasks, report_date, diff_snippets)
        return self._validated(self._chat(context, system_prompt=self.get_system_prompt(self.context_mode)))

    def summarize_report(self, tasks: list[Task], report_date: date, diff_snippets: dict[str, str] | None = None) -> str | None:
        context = self._build_context(tasks, report_date, diff_snippets)
        return self._validated(self._chat(context, system_prompt=self.get_report_system_prompt(self.context_mode)))

    def summarize_week(self, tasks: list[Task], start_date: date, end_date: date, diff_snippets: dict[str, str] | None = None) -> str | None:
        context = self._build_week_context(tasks, start_date, end_date, diff_snippets)
        return self._validated(self._chat(context, system_prompt=self.get_week_system_prompt(self.context_mode)))
