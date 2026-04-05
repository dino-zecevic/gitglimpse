# gitglimpse Reference

> Version 0.1.7 | Python 3.11+ | MIT License

---

## Table of Contents

- [CLI Commands](#cli-commands)
- [Configuration](#configuration)
- [Modes](#modes)
- [--context flag](#--context-flag)
- [--group flag](#--group-flag)
- [Noise filtering](#noise-filtering)
- [Effort estimation](#effort-estimation)
- [Task grouping](#task-grouping)
- [Ticket extraction](#ticket-extraction)
- [Vague messages](#vague-messages)
- [Multi-project](#multi-project)
- [Claude Code / Cursor](#claude-code--cursor)
- [LLM validation](#llm-validation)
- [LLM providers](#llm-providers)
- [Date defaults](#date-defaults)

---

## CLI Commands

### glimpse standup

Generate a standup update from recent git commits.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--json` | bool | `false` | Output as JSON. |
| `--no-llm` | bool | `false` | Skip LLM; use template formatter. |
| `--local-llm` | bool | `false` | Force local LLM (Ollama) regardless of config. |
| `--local-llm-url` | string | (from config) | Override local LLM base URL. |
| `--model` | string | (from config) | Override LLM model name. |
| `--since` | string | smart default | Commits since this date. Accepts git date strings. |
| `--author` | string | (from config) | Filter by author email. |
| `--repo` | string | cwd | Path to git repository. |
| `--repos` | string | (auto) | Comma-separated repo paths for multi-project. |
| `--context` | string | (from config) | `commits`, `diffs`, or `both`. |
| `--group` | string | (from config) | `project` or `task` (multi-project only). |
| `--filter-noise / --no-filter-noise` | bool | (from config) | Toggle noise commit filtering. |
| `--format` | string | `default` | `default` (Rich) or `markdown`. |
| `--output`, `-o` | string | (none) | Save output to file. |
| `--provider` | string | (hidden) | Provider override: `openai`, `anthropic`, `gemini`, `local`. |
| `--skip-setup` | bool | (hidden) | Skip first-run onboarding. |

- `--format markdown` uses the LLM's report prompt (if active) or the Markdown formatter.
- `--since` priority: CLI value > config `default_since` > smart weekday default.
- `--author` priority: CLI value > config `author_email` > all authors.

---

### glimpse week

Generate a weekly summary from git commits.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--json` | bool | `false` | Output as JSON. |
| `--no-llm` | bool | `false` | Skip LLM; use template formatter. |
| `--local-llm` | bool | `false` | Force local LLM (Ollama). |
| `--local-llm-url` | string | (from config) | Override local LLM base URL. |
| `--model` | string | (from config) | Override LLM model name. |
| `--since` | string | `"7 days ago"` | Start of week range. |
| `--until` | string | today | End of week range. |
| `--author` | string | (from config) | Filter by author email. |
| `--repo` | string | cwd | Path to git repository. |
| `--repos` | string | (auto) | Comma-separated repo paths for multi-project. |
| `--context` | string | (from config) | `commits`, `diffs`, or `both`. |
| `--filter-noise / --no-filter-noise` | bool | (from config) | Toggle noise commit filtering. |
| `--provider` | string | (hidden) | Provider override. |
| `--skip-setup` | bool | (hidden) | Skip first-run onboarding. |

---

### glimpse pr

Generate a pull request summary from the current branch.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--json` | bool | `false` | Output as JSON. |
| `--no-llm` | bool | `false` | Skip LLM; use template formatter. |
| `--local-llm` | bool | `false` | Force local LLM (Ollama). |
| `--local-llm-url` | string | (from config) | Override local LLM base URL. |
| `--model` | string | (from config) | Override LLM model name. |
| `--base` | string | `"main"` | Base branch to compare against. |
| `--repo` | string | cwd | Path to git repository. |
| `--context` | string | `"both"` | `commits`, `diffs`, or `both`. Defaults to `both` (overrides config). |
| `--filter-noise / --no-filter-noise` | bool | (from config) | Toggle noise commit filtering. |
| `--provider` | string | (hidden) | Provider override. |
| `--skip-setup` | bool | (hidden) | Skip first-run onboarding. |

- Uses `git log base..HEAD` to find branch-only commits.
- Extracts ticket IDs from branch name automatically.
- Single-repo only (no `--repos` support).

---

### glimpse config show

Display current configuration as a table.

### glimpse config setup

Re-run the interactive setup wizard. Pre-populates current values as defaults.

---

### glimpse init

Create slash-command files for Claude Code and/or Cursor.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--cursor` | bool | `false` | Create `.cursor/commands/` files. |
| `--claude` | bool | `false` | Create `.claude/commands/` files. |
| `--force` | bool | `false` | Overwrite existing files without prompting. |
| `--repo` | string | cwd | Target repository root. |

- No flags or `--claude` only: creates Claude Code commands.
- `--cursor` only: creates Cursor commands only.
- `--claude --cursor`: creates both.

---

## Configuration

Config file: `~/.config/gitglimpse/config.toml` (created automatically on first save).

| Setting | Type | Default | Valid Values | Description |
|---------|------|---------|--------------|-------------|
| `default_mode` | string | `"template"` | `template`, `local-llm`, `api` | Summarization mode. |
| `llm_provider` | string | (none) | `openai`, `anthropic`, `gemini`, `local` | Cloud API provider. Only used when `default_mode = "api"`. |
| `llm_model` | string | (none) | any model name | Model name. Defaults: `gpt-4o-mini`, `claude-sonnet-4-20250514`, `gemini-2.5-flash`, `qwen2.5-coder:latest`. |
| `local_llm_url` | string | `"http://localhost:11434/v1"` | any URL | Local LLM server URL. Must expose OpenAI-compatible `/v1/chat/completions`. |
| `api_key_env` | string | (none) | env var name | Environment variable containing the API key. |
| `author_email` | string | (none) | email address | Default author filter. Unset = all authors. |
| `default_since` | string | `"yesterday"` | any git date string | Default `--since` for standup. |
| `context_mode` | string | `"commits"` | `commits`, `diffs`, `both` | Detail level for LLM prompts and JSON output. |
| `group_by` | string | `"project"` | `project`, `task` | Multi-project standup grouping. |
| `filter_noise` | bool | `true` | `true`, `false` | Filter noise commits by default. |

Settings with null values are omitted from the TOML file. Missing keys use dataclass defaults.

---

## Modes

### Template

`default_mode = "template"` — No LLM. Works offline. Instant results via built-in formatters.

### Local LLM

`default_mode = "local-llm"` — OpenAI-compatible local server (Ollama, LM Studio, etc.).

- Default URL: `http://localhost:11434/v1`
- Default model: `qwen2.5-coder:latest`
- Auto-detects models from `/models` endpoint if none configured.
- Availability check before each request; falls back to template if unreachable.
- Read timeout: 240s. Can be forced with `--local-llm` on any command.

### Cloud API

`default_mode = "api"` — Uses `api_key_env` to read the key from environment. Falls back to template if key is missing.

See [LLM providers](#llm-providers) for endpoint details.

### JSON

`--json` on any command. Structured output to stdout; all other output to stderr.

**JSON schema per command:**

- **standup**: `date`, `since`, `days[]`, `total_estimated_hours`, `effort_note`
- **week**: `period` (start/end), `days[]`, `week_total_hours`, `total_tasks`, `effort_note`
- **pr**: `branch`, `base`, `ticket`, `summary`, `tasks[]`, `files_changed`, `total_insertions`, `total_deletions`, `total_commits`, `estimated_hours`, `effort_note`

**Task object**: `summary`, `branch`, `ticket`, `commits`, `insertions`, `deletions`, `estimated_minutes`, `commit_messages` (omitted in diffs-only mode), `diff_snippet` (optional), `project` (optional).

---

## --context flag

Controls detail level for LLM prompts and JSON output.

| Value | Behavior |
|-------|----------|
| `commits` | Commit messages only. No diffs collected. Fastest. |
| `diffs` | Code diffs only. Commit messages excluded from LLM context (still in JSON unless mode is `diffs`). |
| `both` | Commit messages + code diffs. Richest context, best LLM results. |

- Diffs collected via `git show --patch -U2 <hash>`, max 50 lines per commit.
- In `commits` mode, diffs are still collected for vague-message commits.
- JSON `diff_snippet` capped at 40 lines per task.
- `glimpse pr` defaults to `both` regardless of config.

---

## --group flag

Controls multi-project standup grouping. Only affects `glimpse standup` with multiple projects.

| Value | Behavior |
|-------|----------|
| `project` | **(Default)** Tasks grouped under project name headings, then by day. |
| `task` | Flat chronological list by day. Project name shown inline per bullet. |

No effect in single-project mode.

---

## Noise filtering

Enabled by default (`filter_noise = true`). Toggle per-command with `--filter-noise` / `--no-filter-noise`.

**Message patterns** (commit excluded if message matches):
- **Exact** (case-insensitive): `lint`, `format`, `formatting`
- **Starts with**: `merge branch`, `merge pull request`, `bump`
- **Contains**: `bump version`, `bump dependencies`
- **Keywords**: `run formatter`, `lint fix`, `auto-format`, `format code`, `apply formatting`, `prettier`, `eslint fix`, `update lock file`, `update lockfile`, `regenerate lock`

**File patterns** (commit excluded only if **all** files match):
- **Names**: `package-lock.json`, `yarn.lock`, `poetry.lock`, `Pipfile.lock`, `go.sum`, `pnpm-lock.yaml`, `.prettierrc`, `.prettierignore`, `.eslintrc`, `.eslintrc.json`, `.eslintrc.js`, `.editorconfig`, `.stylelintrc`, `.DS_Store`
- **Patterns**: `*.min.js`, `*.min.css`, `*.map`, `.github/workflows/*.yml`/`.yaml`, `*.pyc`, `__pycache__/`

Commits with a mix of noise and real files are kept. Filtered count appears in output and JSON (`filtered_commits`).

---

## Effort estimation

Each task gets an `estimated_minutes` value from commit timing:

1. Merge commits contribute 0 time.
2. First non-merge commit: +**30 min** assumed prior work.
3. Gaps between consecutive non-merge commits:
   - < 2 hours: add actual gap.
   - >= 2 hours: add capped **45 min** (break assumed).
4. Total lines < 20 AND any gap >= 2h: floor at **30 min** (debugging sessions).
5. Total lines > 200: multiply by **1.2x** (complexity).
6. Minimum: **15 min**.

---

## Task grouping

Commits are grouped into tasks via branch + time-gap:

1. **Bucket by branch** — from ref decorations, `--source` data, or current branch fallback.
2. **Sort oldest-first** within each bucket.
3. **Split at 3-hour gaps** between consecutive commits.
4. **Build metadata** — summary, insertions/deletions, estimated duration, ticket ID.

**Summary derivation:**
- Use the longest non-vague, non-merge commit message.
- If all vague, derive from file paths:
  - Semantic rules: test files -> "Added tests", migrations/SQL -> "Database migration", config -> "Configuration changes", docs/markdown -> "Documentation updates".
  - Fallback: top 2 most-touched directories (e.g., "Changes in src/, tests/").
  - Final fallback: "Various changes".

---

## Ticket extraction

Extracted automatically from branch names.

| Pattern | Example | Result |
|---------|---------|--------|
| GitHub (`#N` or `gh-N`) | `feat/gh-15-auth` | `#15` |
| JIRA (`PROJ-123`) | `feature/PROJ-123-login` | `PROJ-123` |

GitHub-style checked first (prevents `GH-7` from matching as JIRA).

---

## Vague messages

A commit message is vague if:
- Fewer than 4 characters.
- Single known word: `fix`, `fixes`, `fixed`, `update`, `updates`, `updated`, `wip`, `asdf`, `test`, `testing`, `changes`, `change`, `stuff`, `minor`, `misc`, `temp`, `cleanup`, `refactor`, `refactoring`, `done`, `ok`, `works`.

Vague commits get diff collection for better context. In template mode, summaries fall back to file-path heuristics. In LLM mode, diffs are included in the prompt.

---

## Multi-project

**Explicit**: `--repos "path/to/api,path/to/frontend"` — comma-separated, validated as git repos.

**Auto-detection**: if cwd is not a git repo, scans immediate subdirectories (skips hidden dirs).

**Behavior:**
- Each repo collected independently with same filters.
- Tasks tagged with project name (directory name) and merged chronologically.
- JSON includes `multi_project: true` and per-project `projects` array.
- Single-project mode (cwd is a repo or `--repo` used): no project tagging.

---

## Claude Code / Cursor

`glimpse init` creates four slash-command files:

| File | Command run | Output format |
|------|------------|---------------|
| `standup.md` | `glimpse standup --json --context both` | Standup with day-grouped bullets |
| `report.md` | `glimpse standup --json --context both` | Markdown daily report with headings and change stats |
| `week.md` | `glimpse week --json --context both` | Weekly summary with themes and highlights |
| `pr.md` | `glimpse pr --json --context both` | PR description with summary, changes, and stats |

Files are placed in `.claude/commands/` or `.cursor/commands/` depending on flags.

---

## LLM validation

LLM responses are rejected if:
- Length > 2000 characters
- Contains triple backticks or Markdown table separators (`|---|`, `|:--`)
- More than 3 Markdown header lines
- Contains garbage phrases: `would you like`, `let me help`, `next steps`, `which would you`, `shall i`, `here's what`, `current state analysis`
- More than 5 numbered list items

On rejection, falls back to template with a stderr warning. All LLM errors (auth, rate limit, timeout, connection) also fall back to template — the tool never crashes due to LLM failures.

---

## LLM providers

| Provider | Endpoint | Default Model | Auth | Timeouts |
|----------|----------|---------------|------|----------|
| OpenAI | `api.openai.com/v1/chat/completions` | `gpt-4o-mini` | `Authorization: Bearer` via `OPENAI_API_KEY` | 30s connect, 120s read |
| Anthropic | `api.anthropic.com/v1/messages` | `claude-sonnet-4-20250514` | `x-api-key` via `ANTHROPIC_API_KEY` (max 1024 tokens) | 30s connect, 120s read |
| Gemini | `generativelanguage.googleapis.com/v1beta` | `gemini-2.5-flash` | Query param via `GEMINI_API_KEY` | 30s connect, 120s read |
| Local | `localhost:11434/v1/chat/completions` | `qwen2.5-coder:latest` | None | 30s connect, 240s read |

---

## Date defaults

`glimpse standup` `--since` default adapts to the day of the week:

| Day | Default |
|-----|---------|
| Monday | `"last friday"` |
| Tuesday–Friday | `"yesterday"` |
| Saturday–Sunday | `"last friday"` |

Accepted formats: ISO dates (`2025-03-15`), `"N days ago"`, `"yesterday"`, `"last friday"`, any git `--since` string.
