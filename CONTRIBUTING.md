# Contributing to gitglimpse

Thanks for your interest. Contributions are welcome.

---

## Setup

```bash
git clone https://github.com/dino/gitglimpse.git
cd gitglimpse
pip install -e ".[llm]"
```

This installs the `glimpse` entry point in editable mode alongside all optional dependencies.

---

## Running tests

```bash
python -m pytest
```

All tests should pass. The suite covers git parsing, commit grouping, effort estimation, and output formatting — no network calls, no LLM required.

---

## Project layout

```
src/gitglimpse/
├── __init__.py          # package version
├── cli.py               # Typer commands (standup, report, week, config, init)
├── git.py               # git log parsing → Commit dataclass
├── grouping.py          # Commit → Task grouping (branch + time proximity)
├── estimation.py        # Effort estimation + format_duration()
├── config.py            # TOML config load/save via platformdirs
├── formatters/
│   ├── template.py      # Plain-text standup + weekly summary
│   ├── markdown.py      # Markdown daily report
│   └── json.py          # JSON output for piping / slash commands
├── providers/
│   ├── base.py          # BaseLLMProvider ABC + shared prompt helpers
│   ├── local.py         # Ollama / OpenAI-compatible local endpoint
│   ├── openai.py        # OpenAI chat completions
│   ├── claude.py        # Anthropic Messages API
│   ├── gemini.py        # Google Gemini generateContent
│   └── __init__.py      # get_provider() factory
└── commands/
    ├── standup.md        # Claude Code / Cursor slash-command template
    ├── report.md
    └── week.md
```

Data flow: `git log` → `git.py` → `grouping.py` → `estimation.py` → formatter or LLM provider → CLI output.

---

## Adding a new LLM provider

1. Create `src/gitglimpse/providers/myprovider.py` — subclass `BaseLLMProvider` from `providers/base.py` and implement `summarize_standup`, `summarize_report`, and `summarize_week`.
2. Register it in `providers/__init__.py`'s `get_provider()` factory.
3. Add a provider choice to `config_setup()` in `cli.py`.

---

## Code style

- Type hints are required on all public functions and method signatures.
- No external formatter is mandated, but keep lines under 100 characters.
- Keep the `[llm]` extra optional — core commands must work without `httpx`.

---

## Submitting changes

Open a pull request against `main`. Please include a brief description of the change and, if adding behaviour, a test.
