Generate a release changelog from your git history.

Run the following shell command and capture its output:

```
glimpse changelog --json --context both
```

This compares the latest tag to HEAD by default. To target a specific range, pass refs:

```
glimpse changelog --json --from v1.2.0 --to v1.3.0
```

Then format the JSON result into a **changelog** using this structure:

```
# Changelog — [range]

[If "breaking_changes" is non-empty:]
## ⚠ Breaking Changes
- [subject][" (TICKET, hash)" using the entry's ticket/hash if present]

[For each entry in "sections" (already ordered):]
## [heading]
- [subject][" (TICKET, hash)" using the entry's ticket/hash if present]
```

Rules:
- Preserve the section order from the "sections" array; skip any section with no entries.
- Rewrite each entry's "subject" as a clear, user-facing change — but do not invent or drop entries.
- Include the entry "ticket" and short "hash" in parentheses when present.
- List breaking changes first under the "⚠ Breaking Changes" heading.
- If the JSON includes a "filtered_commits" count (> 0), note it briefly at the bottom: "X noise commits filtered".
- If "sections" is empty, write "No changes found in this range."
- No commentary, suggestions, or next steps — only the changelog.
