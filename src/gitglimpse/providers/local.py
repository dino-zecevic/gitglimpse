"""Local LLM provider (e.g. Ollama)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import httpx

from gitglimpse.providers.base import BaseLLMProvider, _warn, validate_llm_output

if TYPE_CHECKING:
    from gitglimpse.grouping import Task

_CONNECT_TIMEOUT = 30.0
_READ_TIMEOUT = 240.0
_AVAILABILITY_TIMEOUT = 3.0
_DEFAULT_MODEL = "qwen2.5-coder:latest"


class LocalProvider(BaseLLMProvider):
    """OpenAI-compatible local LLM (Ollama, LM Studio, etc.)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str | None = None,
        context_mode: str = "commits",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._explicit_model = model
        self._model_resolved = bool(model)
        self.model: str = model or _DEFAULT_MODEL
        self.context_mode = context_mode
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

    def _auto_detect_model(self) -> None:
        """If no model was explicitly chosen, query the server for available models."""
        if self._model_resolved:
            return
        self._model_resolved = True
        try:
            resp = httpx.get(
                f"{self.base_url}/models",
                timeout=_AVAILABILITY_TIMEOUT,
            )
            resp.raise_for_status()
            models = resp.json().get("data", [])
            if models:
                self.model = models[0]["id"]
        except Exception:
            pass  # keep the default

    def _chat(self, user_message: str, system_prompt: str | None = None) -> str | None:
        self._auto_detect_model()
        url = f"{self.base_url}/chat/completions"
        if system_prompt is None:
            system_prompt = self.get_system_prompt()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
        try:
            with _warn.status(f"[dim]Generating with {self.model}...[/dim]"):
                resp = httpx.post(url, json=payload, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except httpx.ConnectError:
            _warn.print(f"[yellow]⚠ Local LLM: connection refused at {url}[/yellow]")
        except httpx.TimeoutException:
            _warn.print(
                f"[yellow]⚠ Model {self.model} timed out after {int(_READ_TIMEOUT)}s. "
                f"Larger models are slower — try a smaller model or enable GPU acceleration in Ollama.[/yellow]"
            )
        except httpx.HTTPStatusError as exc:
            _warn.print(f"[yellow]⚠ Local LLM: HTTP {exc.response.status_code} at {url}[/yellow]")
        except Exception as exc:
            _warn.print(f"[yellow]⚠ Local LLM: unexpected error at {url} — {exc}[/yellow]")
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

    def summarize_standup(
        self,
        tasks: list[Task],
        report_date: date,
        diff_snippets: dict[str, str] | None = None,
    ) -> str | None:
        context = self._build_context(tasks, report_date, diff_snippets)
        prompt = self.get_system_prompt(context_mode=self.context_mode)
        return self._validated(self._chat(context, system_prompt=prompt))

    def summarize_report(
        self,
        tasks: list[Task],
        report_date: date,
        diff_snippets: dict[str, str] | None = None,
    ) -> str | None:
        context = self._build_context(tasks, report_date, diff_snippets)
        prompt = self.get_report_system_prompt(context_mode=self.context_mode)
        return self._validated(self._chat(context, system_prompt=prompt))

    def summarize_week(
        self,
        tasks: list[Task],
        start_date: date,
        end_date: date,
        diff_snippets: dict[str, str] | None = None,
    ) -> str | None:
        context = self._build_week_context(tasks, start_date, end_date, diff_snippets)
        prompt = self.get_week_system_prompt(context_mode=self.context_mode)
        return self._validated(self._chat(context, system_prompt=prompt))
