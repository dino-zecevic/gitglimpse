# gitglimpse

Extract structured context from your git history — PR descriptions, standups, weekly reports, and LLM-ready JSON.

## Install

```bash
pip install gitglimpse
```

## What it does

gitglimpse reads your git log, groups commits into logical tasks, filters noise, extracts ticket IDs from branch names, and outputs structured context — as formatted text or clean JSON.

## Commands

```bash
glimpse pr                          # PR summary from current branch
glimpse standup                     # daily context from recent commits
glimpse week                        # weekly summary grouped by day
glimpse report                      # markdown report with file details
glimpse init                        # generate Claude Code / Cursor slash commands
glimpse config setup                # interactive configuration
```

## Features

- **Noise filtering** — merge commits, lock files, and formatting changes excluded by default
- **Ticket detection** — branch names like `feature/PROJ-123` are parsed automatically
- **Multi-project** — run from a parent directory to aggregate across repos
- **LLM-optional** — works instantly without AI, or connect Ollama / OpenAI / Anthropic / Gemini for richer output
- **Editor integration** — slash commands for Claude Code and Cursor
- **GitHub Action** — auto-generate PR context on every pull request
- **JSON output** — every command supports `--json` for pipelines and LLM workflows

## Links

- **Website:** [gitglimpse.com](https://gitglimpse.com)
- **GitHub:** [github.com/dino-zecevic/gitglimpse](https://github.com/dino-zecevic/gitglimpse)
- **Documentation:** [README on GitHub](https://github.com/dino-zecevic/gitglimpse#readme)

## License

MIT
