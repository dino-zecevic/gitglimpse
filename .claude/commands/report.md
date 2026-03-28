Run the following shell command and capture its output:

```
glimpse report --json
```

Wait — `glimpse report` does not have a `--json` flag. Instead run:

```
glimpse standup --json
```

Then format the JSON result into a **Markdown daily report** using this structure:

```markdown
# Daily Report — [date formatted as "Month D, YYYY"]

## [branch or "unknown"] — [commits] commit(s), ~[estimated_minutes/60 rounded]h

**Files:** [comma-separated list of commit_messages as a proxy; or note "see commit history"]
**Changes:** +[insertions] −[deletions]

[Plain-English description of what was accomplished, derived from the task summary
and commit_messages. 2–4 sentences max. Professional but direct.]
```

Rules:
- One level-2 section per task in the "tasks" array.
- Derive the description from "summary" and "commit_messages" — do not invent work.
- If insertions + deletions > 200, note it was a substantial change set.
- If the tasks array is empty, write "No commits found for this period."
- Use standard Markdown; no HTML.
