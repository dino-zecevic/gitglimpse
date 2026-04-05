# gitglimpse PR Context Action

Auto-generate structured PR descriptions from your git history. Part of [gitglimpse](https://github.com/dino-zecevic/gitglimpse).

## Basic usage (template mode)
```yaml
name: PR Context
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  context:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - run: git fetch origin main:main
      - uses: dino-zecevic/gitglimpse@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

Works out of the box — no API key needed. Uses commit messages and file paths to generate a structured PR summary.

## With LLM (richer descriptions)

Add your API key as a [GitHub secret](https://docs.github.com/en/actions/security-guides/encrypted-secrets) and specify the provider:
```yaml
      - uses: dino-zecevic/gitglimpse@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          llm-provider: openai
          llm-api-key: ${{ secrets.OPENAI_API_KEY }}
          llm-model: gpt-4o-mini
```

The LLM reads actual code diffs and generates richer, more accurate descriptions. Supports OpenAI, Anthropic, and Gemini.

If no API key is provided, the action silently falls back to template mode — it never fails due to missing credentials.

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| github-token | Yes | ${{ github.token }} | GitHub token for posting comments |
| base-branch | No | main | Base branch to compare against |
| context-mode | No | both | Detail level: commits, diffs, both |
| filter-noise | No | true | Filter merge/lint/lock commits |
| llm-provider | No | none | LLM provider: none, openai, anthropic, gemini |
| llm-api-key | No | (empty) | API key for LLM provider (use GitHub secrets) |
| llm-model | No | (empty) | Model name (e.g. gpt-4o-mini) |

## What it does

On every PR, gitglimpse:
1. Analyzes the commits on your branch
2. Groups them into logical tasks
3. Extracts ticket IDs from branch names
4. Filters noise (merges, lock files, formatting)
5. Posts a structured context summary as a PR comment
6. (Optional) Uses an LLM to read diffs and write richer descriptions

The comment updates on each push — no duplicate comments.

## Example output

The action posts a comment like this on your PR:

> ### PR Context (gitglimpse)
>
> **Summary:** Refactored auth middleware to support JWT rotation.
>
> **Ticket:** `AUTH-42`
>
> **Changes:**
> - Add JWT refresh handler with token rotation (AUTH-42) (~1h)
> - Add rate limiting middleware (~0.5h)
> - Add auth test coverage (~0.5h)
>
> **Files:** auth.py, middleware.py, tests/test_auth.py
>
> **Stats:** 5 commits · +142 / -8 · ~2h estimated effort
>
> *2 noise commits filtered*

## Requirements

- The checkout step must use `fetch-depth: 0` (full history)
- The `git fetch origin main:main` step ensures the base branch is available for comparison
- The job needs `pull-requests: write` permission
