"""OpenAI provider."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import httpx

from gitglimpse.providers.base import BaseLLMProvider, _warn

if TYPE_CHECKING:
    from gitglimpse.grouping import Task

_API_URL = "https://api.openai.com/v1/chat/completions"
_TIMEOUT = httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI chat completions provider."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.model = model

    def _chat(self, user_message: str) -> str | None:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": user_message},
            ],
        }
        try:
            resp = httpx.post(_API_URL, json=payload, headers=headers, timeout=_TIMEOUT)
            if resp.status_code == 401:
                _warn.print("[yellow]⚠ OpenAI: invalid API key.[/yellow]")
                return None
            if resp.status_code == 429:
                _warn.print("[yellow]⚠ OpenAI: rate limit reached.[/yellow]")
                return None
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            _warn.print("[yellow]⚠ OpenAI: request timed out.[/yellow]")
        except httpx.HTTPStatusError as exc:
            _warn.print(f"[yellow]⚠ OpenAI: HTTP {exc.response.status_code}.[/yellow]")
        except Exception as exc:
            _warn.print(f"[yellow]⚠ OpenAI: unexpected error — {exc}.[/yellow]")
        return None

    def summarize_standup(self, tasks: list[Task], report_date: date) -> str | None:
        context = self._format_tasks_context(tasks, report_date)
        return self._chat(
            f"Generate a standup update from the following commit data:\n\n{context}"
        )

    def summarize_report(self, tasks: list[Task], report_date: date) -> str | None:
        context = self._format_tasks_context(tasks, report_date)
        return self._chat(
            f"Generate a daily Markdown report from the following commit data:\n\n{context}"
        )

    def summarize_week(
        self, tasks: list[Task], start_date: date, end_date: date
    ) -> str | None:
        context = self._format_week_context(tasks, start_date, end_date)
        return self._chat(
            "Generate a weekly summary with key themes and highlights "
            f"from the following commit data:\n\n{context}"
        )
