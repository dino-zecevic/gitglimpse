Generate a detailed daily report from your git commits.

Run the following shell command and capture its output:

```
glimpse standup --json
```

Then format the JSON result into a **Markdown daily report** using this structure:

```markdown
# Daily Report — [date formatted as "Month D, YYYY"]

[For each entry in the "days" array:]
## [entry "label"] — [entry "date"]

[For each task in the day's "tasks" array:]
### [branch or "general"] — [commits] commit(s), ~[estimated_minutes/60 rounded]h

**Changes:** +[insertions] −[deletions]

[Plain-English description of what was accomplished, derived from the task summary
and commit_messages. 2–4 sentences max. Professional but direct.]
```

Rules:
- Iterate the "days" array in order. Each day becomes a level-2 section.
- One level-3 section per task within each day.
- Derive the description from "summary" and "commit_messages" — do not invent work.
- If insertions + deletions > 200, note it was a substantial change set.
- Do NOT add a section with plans or next steps. Only report completed work.
- If the "days" array is empty, write "No commits found for this period."
- Use standard Markdown; no HTML.
