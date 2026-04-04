Generate a pull request summary from your current branch.

Run the following shell command and capture its output:

```
glimpse pr --json --context both
```

Then format the JSON result into a clean PR description using this structure:

```
## Summary

[One paragraph describing what this branch does, derived from the "summary" field
and the task summaries. Be specific about what was changed. 2–4 sentences.]

## Changes

[For each task in the "tasks" array:]
- [task "summary"][" (TICKET)" if task "ticket" is non-null] (~[estimated_minutes / 60 rounded to 1 decimal]h)

## Stats

- [total_commits] commits
- +[total_insertions] / -[total_deletions]
- Estimated effort: ~[estimated_hours]h
[- Ticket: [ticket] — only if "ticket" is non-null]
```

Rules:
- The "summary" field at the top level is a combined summary — use it as the basis for the Summary paragraph.
- If tasks include "commit_messages", use them to add specifics to the Summary paragraph.
- If tasks include "diff_snippet", use it for more accurate descriptions.
- If the JSON includes a "filtered_commits" count (> 0), mention it briefly: "X noise commits filtered".
- Do NOT add suggestions, code review comments, or questions. Only describe completed work.
- Do NOT invent changes not present in the data.
- Keep the Summary paragraph under 4 sentences.
- Use developer language: concise and direct.
- If the "tasks" array is empty, write "No commits found on this branch."
