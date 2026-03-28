Run the following shell command and capture its output:

```
glimpse week --json
```

Then format the JSON result into a **weekly summary** using this structure:

```
Weekly Summary — [period.start to period.end, formatted as "Month D–D, YYYY" or "Month D – Month D, YYYY"]

[day_name] ([date formatted as "Month D"]):
- [task summary] (~[estimated_minutes/60 rounded]h)
Day total: [total_hours]h

[Repeat for each day in the "days" array that has tasks]

Key themes:
- [3–5 bullet points identifying the main areas of work across the whole week,
   inferred from task summaries and commit_messages]

Highlights:
- [1–3 notable accomplishments — largest change sets, most complex features, etc.]

Week total: [week_total_hours]h across [total_tasks] tasks
```

Rules:
- Only include days that appear in the "days" array (skip days with no commits).
- Key themes and Highlights must be inferred from the actual data — do not invent.
- Keep each theme/highlight bullet under 100 characters.
- If the days array is empty, write "(no commits found this week)".
- Use developer language: concise and direct.
