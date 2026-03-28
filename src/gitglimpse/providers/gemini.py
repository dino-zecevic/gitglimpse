"""Google Gemini provider."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import httpx

from gitglimpse.providers.base import BaseLLMProvider, _warn

if TYPE_CHECKING:
    from gitglimpse.grouping import Task

_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_TIMEOUT = httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0)


class GeminiProvider(BaseLLMProvider):
    """Google Gemini generateContent provider."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self.api_key = api_key
        self.model = model

    def _chat(self, user_message: str) -> str | None:
        url = f"{_API_BASE}/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {
                "parts": [{"text": self.get_system_prompt()}]
            },
            "contents": [
                {"parts": [{"text": user_message}]}
            ],
        }
        try:
            resp = httpx.post(url, json=payload, timeout=_TIMEOUT)
            if resp.status_code == 400:
                _warn.print("[yellow]⚠ Gemini: bad request (check API key or model name).[/yellow]")
                return None
            if resp.status_code == 429:
                _warn.print("[yellow]⚠ Gemini: rate limit reached.[/yellow]")
                return None
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except httpx.TimeoutException:
            _warn.print("[yellow]⚠ Gemini: request timed out.[/yellow]")
        except httpx.HTTPStatusError as exc:
            _warn.print(f"[yellow]⚠ Gemini: HTTP {exc.response.status_code}.[/yellow]")
        except Exception as exc:
            _warn.print(f"[yellow]⚠ Gemini: unexpected error — {exc}.[/yellow]")
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
