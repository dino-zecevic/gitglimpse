# gitglimpse

> Turn your git history into standup updates, daily reports, and weekly summaries — in seconds.

<!-- GIF_PLACEHOLDER — record with asciinema or vhs and replace this line -->

gitglimpse reads your `git log`, groups commits into logical tasks, estimates how long each took, and formats everything as a standup, a Markdown report, or a weekly digest. Optionally, it hands that context to an LLM (local or API) for a polished write-up.

---

## Quick start

```bash
pip install "gitglimpse[llm]"   # [llm] pulls in httpx for LLM provider support
cd your-project
glimpse standup
```

---

## Commands

### `glimpse standup`

Generate a plain-text standup update from yesterday's commits.

```bash
glimpse standup                       # template output (no LLM required)
glimpse standup --since "2 days ago"  # extend the look-back window
glimpse standup --json                # machine-readable JSON for piping
glimpse standup --local-llm           # polish with a local Ollama model
```

Template output:

```
Standup — March 27, 2026

Yesterday:
  • Implement OAuth2 login flow (feature/auth, ~1.5h)
  • Fix null pointer in payment handler (main, ~0.5h)

Today:
  • Continue working on Implement OAuth2 login flow
  • Follow up on Fix null pointer in payment handler

Total estimated time: 2.0h
```

---

### `glimpse report`

Generate a daily Markdown report — good for engineering journals or async team updates.

```bash
glimpse report                   # print to terminal
glimpse report -o daily.md       # save to file
glimpse report --since 2025-03-01
```

---

### `glimpse week`

Generate a weekly digest grouped by day, with key themes and highlights when an LLM is available.

```bash
glimpse week
glimpse week --since "14 days ago" --until "7 days ago"
glimpse week --json
```

---

### `glimpse init`

Write `/standup`, `/report`, and `/week` slash-command files into your project so Claude Code (and optionally Cursor) can run glimpse for you without leaving the editor.

```bash
glimpse init              # creates .claude/commands/{standup,report,week}.md
glimpse init --cursor     # also creates .cursor/commands/
glimpse init --force      # overwrite without prompting
```

After running `glimpse init`, commit the generated files:

```bash
git add .claude/commands
git commit -m "chore: add glimpse slash commands"
```

Then type `/standup` in Claude Code to get your update.

---

### `glimpse config`

```bash
glimpse config show    # display current configuration
glimpse config setup   # interactive wizard
```

---

## Output modes

| Mode | How to activate | Requires |
|------|----------------|----------|
| **Template** | default (no flags) | nothing |
| **Local LLM** | `--local-llm` or `glimpse config setup` → option 2 | Ollama running locally |
| **API (BYOK)** | `glimpse config setup` → option 3 | API key for OpenAI / Anthropic / Gemini |
| **JSON** | `--json` (standup + week) | nothing |

**Template mode** is instant and works offline. **LLM modes** send commit context (and truncated diffs for vague commit messages) to the model and return a polished narrative.

---

## Configuration

Run `glimpse config setup` to save your preferences. Settings are stored in:

| OS | Path |
|----|------|
| macOS / Linux | `~/.config/gitglimpse/config.toml` |
| Windows | `%APPDATA%\gitglimpse\config.toml` |

Example `config.toml`:

```toml
default_mode = "api"
llm_provider = "anthropic"
author_email = "you@example.com"
default_since = "yesterday"
local_llm_url = "http://localhost:11434/v1"

[api_keys]
anthropic = "sk-ant-..."
```

CLI flags always override config file values.

---

## Claude Code integration

1. Run `glimpse init` in your project root.
2. Commit the `.claude/commands/` files.
3. In Claude Code, type `/standup` — Claude will run `glimpse standup --json`, parse the output, and write your standup in the chat.

The same workflow works for `/report` and `/week`.

---

## Requirements

- Python 3.11+
- git

Optional (for LLM modes):
- `httpx` (included with `pip install "gitglimpse[llm]"`)
- Ollama (local mode) or an API key (OpenAI / Anthropic / Gemini)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE) for details.
