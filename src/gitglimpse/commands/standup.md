Generate a standup update from your recent git commits.

Run the following shell command and capture its output:

```
glimpse standup --json
```

Then format the JSON result into a clean standup update using **exactly** this structure:

```
Standup — [date from JSON "date" field, formatted as "Month D, YYYY"]

[For each entry in the "days" array:]
[entry "label"]:
- [task "summary"] ([task "branch" if non-empty], ~[estimated_minutes / 60 rounded to 1 decimal]h)

Total estimated time: [total_estimated_hours]h
```

Rules:
- Iterate the "days" array in order. Each day becomes its own section using the "label" field as the header (e.g. "Yesterday:", "Friday:", "Today:").
- One bullet per task in each day's "tasks" array.
- If a task has an empty "branch" field, omit the branch from the parenthetical.
- If a task includes a "diff_snippet" field, use it to write a more accurate description of what was changed.
- Do NOT add a "Today:" section with plans or next steps. Only show completed work from the data.
- Do NOT invent tasks or work items that are not present in the JSON data.
- Keep each bullet under 100 characters.
- Use developer language: concise and direct.
- If the "days" array is empty, write "(no commits found)".
