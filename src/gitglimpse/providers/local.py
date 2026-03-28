"""Local LLM provider (e.g. Ollama)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import httpx

from gitglimpse.providers.base import BaseLLMProvider, _warn

if TYPE_CHECKING:
    from gitglimpse.grouping import Task

_CONNECT_TIMEOUT = 30.0
_READ_TIMEOUT = 120.0
_AVAILABILITY_TIMEOUT = 3.0


class LocalProvider(BaseLLMProvider):
    """OpenAI-compatible local LLM (Ollama, LM Studio, etc.)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "llama3.2",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._timeout = httpx.Timeout(
            connect=_CONNECT_TIMEOUT,
            read=_READ_TIMEOUT,
            write=_CONNECT_TIMEOUT,
            pool=_CONNECT_TIMEOUT,
        )

    def is_available(self) -> bool:
        """Return True if the local server responds to a quick probe."""
        try:
            resp = httpx.get(
                f"{self.base_url}/models",
                timeout=_AVAILABILITY_TIMEOUT,
            )
            return resp.is_success
        except Exception:
            return False

    def _chat(self, user_message: str) -> str | None:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": user_message},
            ],
        }
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except httpx.ConnectError:
            _warn.print("[yellow]⚠ Local LLM: connection refused.[/yellow]")
        except httpx.TimeoutException:
            _warn.print("[yellow]⚠ Local LLM: request timed out.[/yellow]")
        except httpx.HTTPStatusError as exc:
            _warn.print(f"[yellow]⚠ Local LLM: HTTP {exc.response.status_code}.[/yellow]")
        except Exception as exc:
            _warn.print(f"[yellow]⚠ Local LLM: unexpected error — {exc}.[/yellow]")
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
