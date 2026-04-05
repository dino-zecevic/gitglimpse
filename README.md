<div align="center">
  <img src="docs/gitglimpse.png" alt="gitglimpse" width="120">
  <h3>gitglimpse</h3>
  <p>Extract structured context from your git history — PR descriptions, standups, weekly reports, and LLM-ready JSON.</p>

  [![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
  [![PyPI](https://img.shields.io/pypi/v/gitglimpse?style=for-the-badge)](https://pypi.org/project/gitglimpse/)
  [![License: MIT](https://img.shields.io/badge/license-MIT-F59E0B?style=for-the-badge)](LICENSE)
  [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge)](CONTRIBUTING.md)

  <br />
  <a href="https://gitglimpse.com"><strong>Website</strong></a>
  ·
  <a href="#quick-start">Quick Start</a>
  ·
  <a href="https://github.com/dino-zecevic/gitglimpse/issues/new?labels=bug">Report Bug</a>
  ·
  <a href="https://github.com/dino-zecevic/gitglimpse/issues/new?labels=enhancement">Request Feature</a>
</div>

---

<details>
<summary>Table of Contents</summary>

- [About](#about)
- [Quick Start](#quick-start)
- [Commands](#commands)
- [Output Modes](#output-modes)
- [GitHub Action](#github-action)
- [CI/CD Integration](#cicd-integration)
- [Claude Code & Cursor](#claude-code--cursor)
- [Key Features](#key-features)
- [Multi-Project Mode](#multi-project-mode)
- [Configuration](#configuration)
- [Limitations](#limitations)
- [Contributing](#contributing)
- [License](#license)

</details>

---

## About

Modern development — especially with AI — creates more changes across more files than ever. Git tracks what changed, but not in a way that's easy to understand quickly.

gitglimpse reads your git history, filters noise, groups commits into logical tasks, extracts ticket IDs, and outputs structured context that humans and AI tools can consume.

> A context extraction layer for your codebase.

### Built With

* [Python 3.11+](https://python.org)
* [Typer](https://typer.tiangolo.com/) — CLI framework
* [Rich](https://rich.readthedocs.io/) — terminal formatting

---

## Quick Start

```bash
pip install gitglimpse
cd your-project
glimpse standup
```

No API keys, no accounts, no setup required.

---

## Demo

![glimpse pr](docs/demo-pr.gif)

---

## Commands

### `glimpse pr`

Generate a PR summary from your current branch.

```bash
glimpse pr                  # template summary
glimpse pr --json           # structured JSON
glimpse pr --base develop   # compare against develop
```

### `glimpse standup`

Generate a daily summary from recent commits.

```bash
glimpse standup                       # today's context
glimpse standup --json                # structured JSON
glimpse standup --since "3 days ago"  # custom range
glimpse standup --format markdown     # markdown output
```

### `glimpse week`

Weekly breakdown grouped by day.

```bash
glimpse week          # last 7 days
glimpse week --json   # structured JSON
```

### `glimpse init`

Generate slash-command files for Claude Code and Cursor.

```bash
glimpse init                    # Claude Code commands
glimpse init --cursor           # Cursor commands only
glimpse init --claude --cursor  # Claude Code & Cursor commands
```

Creates `/standup`, `/pr`, `/week`, and `/report` commands in your repo.

### `glimpse config`

```bash
glimpse config show    # display current settings
glimpse config setup   # interactive setup wizard
```

---

## Output Modes

| Mode | Flag | Description |
|------|------|-------------|
| Template | (default) | Fast, deterministic, no LLM. Works offline. |
| Local LLM | `--local-llm` | Uses Ollama (must be running on your machine). Privacy-first, fully local. |
| Cloud API | (via config) | OpenAI, Anthropic, or Gemini with your API key. |
| JSON | `--json` | Structured output for pipelines, scripts, and LLM tools. |

---

## GitHub Action

Add automatic PR context comments to your repository.

### Basic (no API key needed)

```yaml
name: PR Context
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  context:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - run: git fetch origin main:main
      - uses: dino-zecevic/gitglimpse@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

### With LLM

```yaml
      - uses: dino-zecevic/gitglimpse@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          llm-provider: openai
          llm-api-key: ${{ secrets.OPENAI_API_KEY }}
          llm-model: gpt-4o-mini
```

Supports `openai`, `anthropic`, and `gemini`. Store your key as a [GitHub secret](https://docs.github.com/en/actions/security-guides/encrypted-secrets). Falls back to template mode if no key is provided.

The comment updates on each push — no duplicates.

See [action/README.md](action/README.md) for all inputs and configuration.

---

## CI/CD Integration

### GitLab CI

```yaml
pr-context:
  stage: test
  script:
    - pip install gitglimpse
    - glimpse pr --skip-setup
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

### Bitbucket Pipelines

```yaml
pipelines:
  pull-requests:
    '**':
      - step:
          name: PR Context
          script:
            - pip install gitglimpse
            - glimpse pr --skip-setup
```

### LLM in any CI

```bash
export OPENAI_API_KEY=$YOUR_SECRET
glimpse pr --provider openai --model gpt-4o-mini --context both --skip-setup
```

---

## Claude Code & Cursor

```bash
glimpse init                          # creates .claude/commands/
git add .claude/commands/ && git commit -m "add glimpse commands"
```

Every developer who pulls the repo gets `/standup`, `/pr`, `/week`, and `/report` as slash commands. The repo is the distribution channel.

For Cursor only: `glimpse init --cursor`
For both: `glimpse init --claude --cursor`

---

## Key Features

### Noise Filtering

Merge commits, lock files, and formatting changes are excluded by default. Only meaningful work appears in output.

```bash
glimpse standup --no-filter-noise   # include everything
```

### Task Grouping

Consecutive commits on the same branch are grouped into logical tasks. 3 commits become 1 task with a derived summary.

### Ticket Extraction

Branch names like `feature/AUTH-42-login` are parsed automatically. Ticket IDs (`AUTH-42`, `#15`) appear in output and JSON.

### Effort Estimation

Approximate effort based on commit timing patterns. Gaps under 2 hours count as work time; longer gaps are capped. Labeled as "estimated effort" — not time tracking.

### Diff Analysis

With `--context both` or `--context diffs`, gitglimpse collects actual code diffs and sends them to the LLM for richer, more accurate summaries.

### Vague Message Handling

When commit messages are vague (`fix`, `wip`, `update`), the tool falls back to file-path-based summaries or uses diffs for context.

---

## Multi-Project Mode

Run from a parent directory to aggregate work across repos:

```bash
cd ~/projects
glimpse standup
```

gitglimpse auto-detects git repos in subdirectories, merges timelines, and groups by project or task.

```bash
glimpse standup --repos "api,frontend,landing"   # explicit repos
glimpse standup --group task                      # flat task list
```

---

## Configuration

```bash
glimpse config setup    # interactive wizard
glimpse config show     # view current settings
```

Config file: `~/.config/gitglimpse/config.toml`

| Setting | Default | Description |
|---------|---------|-------------|
| `default_mode` | `template` | `template`, `local-llm`, or `api` |
| `context_mode` | `commits` | `commits`, `diffs`, or `both` |
| `author_email` | (none) | filter commits by author |
| `filter_noise` | `true` | exclude noise commits |
| `group_by` | `project` | `project` or `task` (multi-project) |
| `llm_provider` | (none) | `openai`, `anthropic`, `gemini`, `local` |
| `llm_model` | (none) | model name for the provider |
| `api_key_env` | (none) | env var name for the API key |

See [FEATURES.md](FEATURES.md) for the complete reference.

---

## Limitations

- Only sees **code changes** — not meetings, research, or documentation work outside git.
- Effort estimation is **heuristic** — useful for memory, not for billing.
- Output quality depends on **commit message quality** in template mode. Use `--context both` with an LLM for results based on actual code diffs.

---

## Contributing

PRs welcome — especially for:

- Better effort estimation algorithms
- Smarter task grouping heuristics
- Improved noise filtering patterns

1. Fork the repo
2. Create your branch (`git checkout -b feature/improvement`)
3. Commit your changes (`git commit -m "Add improvement"`)
4. Push (`git push origin feature/improvement`)
5. Open a Pull Request

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

---

<div align="center">

Built by [Dino](https://dinoze.dev) · [gitglimpse.com](https://gitglimpse.com)

</div>
