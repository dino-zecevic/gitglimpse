Generate a weekly summary of your git activity.

Run the following shell command and capture its output:

```
glimpse week --json --context both
```

Then format the JSON result into a **weekly summary** using this structure:

```
Weekly Summary — [period.start to period.end, formatted as "Month D–D, YYYY" or "Month D – Month D, YYYY"]

[For each entry in the "days" array that has tasks:]
[day_name] ([date formatted as "Month D"]):
- [task summary][" (TICKET)" if task "ticket" is non-null] (~[total_hours for task]h)
Day total: [total_hours]h

Key themes:
- [3–5 bullet points identifying the main areas of work across the whole week,
   inferred from task summaries and commit_messages]

Highlights:
- [1–3 notable accomplishments — largest change sets, most complex features, etc.]

Week total: [week_total_hours]h across [total_tasks] tasks
```

Rules:
- Only include days that appear in the "days" array (skip days with no commits).
- If a task has a "ticket" field (non-null), include it after the summary: "- Implemented auth (PROJ-123) (~2h)".
- Key themes and Highlights must be inferred from the actual data — do not invent.
- If the JSON includes a "filtered_commits" count (> 0), mention it briefly at the top: "X noise commits filtered".
- Do NOT add a section with plans or next steps. Only summarize completed work.
- Keep each theme/highlight bullet under 100 characters.
- If the days array is empty, write "(no commits found this week)".
- Use developer language: concise and direct.
