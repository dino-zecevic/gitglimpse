Run the following shell command and capture its output:

```
glimpse standup --json
```

Then format the JSON result into a clean standup update using **exactly** this structure:

```
Standup — [date from JSON "date" field, formatted as "Month D, YYYY"]

Yesterday:
- [task "summary"] ([task "branch" if non-empty, otherwise omit], ~[estimated_minutes / 60 rounded to 1 decimal]h)

Today:
- [reasonable next step inferred from each yesterday task — e.g. "Continue X", "Follow up on Y"]

Total estimated time: [total_estimated_hours]h
```

Rules:
- One bullet per task in the "tasks" array.
- If a task has an empty "branch" field, omit the branch from the bullet.
- Do NOT invent tasks or work items that are not present in the JSON data.
- Keep each bullet under 100 characters.
- Use developer language: concise and direct.
- If the tasks array is empty, write "(no commits found)" under Yesterday and "(nothing planned)" under Today.
