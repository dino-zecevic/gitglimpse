<div align="center">

<img src="docs/gitglimpse.png" alt="gitglimpse" width="120">

# gitglimpse

**Extract structured context from your git history. Standups, PR descriptions, weekly reports, and LLM-ready JSON — from one command.**

50KB of raw diffs → 1KB of structured signal. Less noise, fewer tokens, better output.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-F59E0B)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)

<br>

</div>

---

## Why gitglimpse?

Modern development (especially with AI) creates **more changes across more files than ever**.

Git tracks *what changed* — but not in a way that's easy to understand quickly.

gitglimpse bridges that gap.

It turns raw git history into:

- **Structured context (JSON)** for LLMs and tools  
- **Standups & reports** for humans  
- **Clean summaries** without opening diffs or PRs  

> Think of it as a **context extraction layer for your codebase**.

---

## Demo

<!-- TODO: Replace with real GIF -->
![Standup Demo](docs/demo-standup.gif)

---

## Quick Start

```bash
pip install gitglimpse
cd your-project
glimpse standup
````

That’s it. No API keys, no setup required.

---

## Core Idea

gitglimpse is not just a “standup generator”.

It’s a **Git → Structured Context engine**.

```bash
glimpse standup --json | your-llm
```

Instead of dumping raw diffs into an LLM, you give it:

* grouped tasks
* extracted tickets
* filtered noise
* optional diffs
* structured JSON

---

## Commands

### `glimpse pr`

Generate PR summaries from your branch.

```bash
glimpse pr
glimpse pr --json
glimpse pr --base develop
```

---

### `glimpse standup`

Generate a daily summary or structured context.

```bash
glimpse standup
glimpse standup --json
glimpse standup --since "3 days ago"
glimpse standup --format markdown
```

Example:

```
Yesterday:
  • Add rate limiting middleware (AUTH-42, ~1.5h)
  • Fix pagination bug (BUG-87, ~1h)

Estimated effort: 2.5h
```

---

### `glimpse week`

Weekly breakdown grouped by day.

```bash
glimpse week
glimpse week --json
```

---

### `glimpse init`

Install Claude Code / Cursor slash commands.

```bash
glimpse init
```

Then in your editor:

```
/standup
/pr
/week
```

---

### `glimpse config`

View or edit configuration.

```bash
glimpse config show
glimpse config setup
```

---

## Output Modes

| Mode          | Description                     |
| ------------- | ------------------------------- |
| **Template**  | Fast, deterministic, no LLM     |
| **Local LLM** | Uses Ollama (privacy-first)     |
| **Cloud API** | OpenAI / Anthropic / Gemini     |
| **JSON**      | Structured output for pipelines |

---

## What Makes It Different

### 1. Noise Filtering (by default)

Removes:

* merge commits
* lock files
* formatting changes

So you only see meaningful work.

---

### 2. Task Grouping

Commits → grouped into **real tasks**:

```
3 commits → 1 task
```

---

### 3. Ticket Extraction

Automatically parses:

```
feature/AUTH-42-login → AUTH-42
```

---

### 4. Works Without LLMs

No AI required.

* Good commits → good summaries
* Bad commits → fallback heuristics
* LLM → optional enhancement

---

### 5. Built for LLM Workflows

Instead of:

```bash
git diff | llm
```

You do:

```bash
glimpse standup --json | llm
```

Cleaner input → better output.

---

## Claude Code Integration

<!-- TODO: Add GIF showing /standup usage -->

```bash
glimpse init
git add .claude/commands/
git commit -m "add glimpse commands"
```

Now every dev on your team gets:

```
/standup
/pr
/week
```

The repo becomes the distribution channel.

---

## GitHub Action

Add automatic PR context to your repository:
```yaml
- uses: dino-zecevic/gitglimpse@main
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

For richer summaries powered by an LLM:
```yaml
- uses: dino-zecevic/gitglimpse@main
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    llm-provider: openai
    llm-api-key: ${{ secrets.OPENAI_API_KEY }}
    llm-model: gpt-4o-mini
```

Every pull request gets a structured summary with changes, ticket IDs, and effort estimates. The comment updates on each push. Without an LLM, template mode runs automatically — no API key needed.

See [action/README.md](action/README.md) for full configuration options.

---

## CI/CD Integration

gitglimpse works in any CI system. The GitHub Action handles comment posting automatically. For GitLab and Bitbucket, run the CLI directly:

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

### Adding LLM in any CI
```bash
export OPENAI_API_KEY=$YOUR_SECRET
glimpse pr --provider openai --model gpt-4o-mini --context both --skip-setup
```

Works with OpenAI, Anthropic, and Gemini. The API key is only used for the single API call during the pipeline run.

---

## Multi-Project Mode

Run from a parent folder:

```bash
cd ~/projects
glimpse standup
```

gitglimpse will:

* detect repos automatically
* merge timelines
* group by project or task

<!-- TODO: Add multi-project GIF -->

---

## Configuration

```bash
glimpse config setup
```

Stored in:

```
~/.config/gitglimpse/config.toml
```

Supports:

* local models (Ollama)
* cloud APIs
* context modes (`commits`, `diffs`, `both`)

---

## Philosophy

* **Privacy-first** — works fully offline
* **LLM-optional** — useful without AI
* **Developer-first** — not a manager tool
* **Composable** — JSON output for pipelines
* **Honest** — no fake precision (effort is approximate)

---

## When It’s Actually Useful

* Weekly summaries across repos
* PR descriptions
* Feeding context into coding agents
* Remembering what you did yesterday

---

## Limitations

* Only sees **code changes** (not meetings, docs, etc.)
* Effort estimation is **heuristic, not accurate**
* Depends on git history quality

---

## Installation

```bash
pip install gitglimpse
```

Requirements:

* Python 3.11+
* git
* (optional) Ollama or API key

---

## Contributing

PRs welcome — especially for:

* better effort estimation
* smarter task grouping
* improved noise filtering

---

## License

MIT

---

<div align="center">

Built by Dino

</div>