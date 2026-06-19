"""Changelog formatting (template, Markdown, and JSON)."""

import json as _json

from rich.markup import escape as _escape

from gitglimpse.git import Commit
from gitglimpse.grouping import (
    CHANGELOG_SECTIONS,
    changelog_subject,
    classify_commit_type,
    extract_ticket_id,
    is_breaking_change,
)


def _range_label(from_ref: str | None, to_ref: str) -> str:
    if from_ref:
        return f"{from_ref}..{to_ref}"
    return to_ref


def _entry(commit: Commit) -> dict:
    """Build a single changelog entry from a commit."""
    return {
        "subject": changelog_subject(commit.message),
        "ticket": extract_ticket_id(commit.message),
        "hash": commit.hash[:7],
        "breaking": is_breaking_change(commit.message),
    }


def build_sections(commits: list[Commit]) -> list[tuple[str, str, list[dict]]]:
    """Group commits into ordered (type_key, heading, entries) sections.

    Merge commits are skipped. Duplicate subjects within a section are collapsed.
    Only sections with at least one entry are returned, in CHANGELOG_SECTIONS order.
    """
    buckets: dict[str, list[dict]] = {key: [] for key, _ in CHANGELOG_SECTIONS}
    seen: dict[str, set[str]] = {key: set() for key, _ in CHANGELOG_SECTIONS}

    for commit in commits:
        if commit.is_merge:
            continue
        key = classify_commit_type(commit.message)
        entry = _entry(commit)
        subject_key = entry["subject"].lower()
        if subject_key in seen[key]:
            continue
        seen[key].add(subject_key)
        buckets[key].append(entry)

    sections: list[tuple[str, str, list[dict]]] = []
    for key, heading in CHANGELOG_SECTIONS:
        if buckets[key]:
            sections.append((key, heading, buckets[key]))
    return sections


def _breaking_entries(sections: list[tuple[str, str, list[dict]]]) -> list[dict]:
    return [e for _, _, entries in sections for e in entries if e["breaking"]]


def _entry_suffix(entry: dict) -> str:
    parts: list[str] = []
    if entry["ticket"]:
        parts.append(entry["ticket"])
    parts.append(entry["hash"])
    return f" ({', '.join(parts)})"


# ---------------------------------------------------------------------------
# Template (Rich markup)
# ---------------------------------------------------------------------------

def format_changelog_template(
    commits: list[Commit],
    from_ref: str | None,
    to_ref: str,
    filtered_count: int = 0,
) -> str:
    """Render a changelog using Rich markup."""
    sections = build_sections(commits)
    label = _range_label(from_ref, to_ref)
    lines: list[str] = [f"[bold yellow]Changelog — {_escape(label)}[/bold yellow]", ""]

    if not sections:
        lines.append("[dim](no changes found in this range)[/dim]")
        return "\n".join(lines)

    breaking = _breaking_entries(sections)
    if breaking:
        lines.append("[bold red]⚠ Breaking Changes[/bold red]")
        for e in breaking:
            lines.append(f"  [red]•[/red] {_escape(e['subject'])}[dim]{_escape(_entry_suffix(e))}[/dim]")
        lines.append("")

    for _key, heading, entries in sections:
        lines.append(f"[bold]{heading}[/bold]")
        for e in entries:
            lines.append(
                f"  [yellow]•[/yellow] {_escape(e['subject'])}"
                f"[dim]{_escape(_entry_suffix(e))}[/dim]"
            )
        lines.append("")

    total = sum(len(entries) for _, _, entries in sections)
    summary = f"[dim]{total} change{'s' if total != 1 else ''}[/dim]"
    if filtered_count > 0:
        summary += f" [dim]· {filtered_count} noise commits filtered[/dim]"
    lines.append(summary)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def format_changelog_markdown(
    commits: list[Commit],
    from_ref: str | None,
    to_ref: str,
    filtered_count: int = 0,
) -> str:
    """Render a changelog as Markdown."""
    sections = build_sections(commits)
    label = _range_label(from_ref, to_ref)
    lines: list[str] = [f"# Changelog — {label}", ""]

    if not sections:
        lines.append("No changes found in this range.")
        return "\n".join(lines)

    breaking = _breaking_entries(sections)
    if breaking:
        lines.append("## ⚠ Breaking Changes")
        lines.append("")
        for e in breaking:
            lines.append(f"- {e['subject']}{_entry_suffix(e)}")
        lines.append("")

    for _key, heading, entries in sections:
        lines.append(f"## {heading}")
        lines.append("")
        for e in entries:
            lines.append(f"- {e['subject']}{_entry_suffix(e)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def format_changelog_json(
    commits: list[Commit],
    from_ref: str | None,
    to_ref: str,
    filtered_count: int = 0,
) -> str:
    """Render a changelog as a JSON string."""
    sections = build_sections(commits)
    data: dict = {
        "from": from_ref,
        "to": to_ref,
        "range": _range_label(from_ref, to_ref),
        "total_changes": sum(len(entries) for _, _, entries in sections),
        "breaking_changes": _breaking_entries(sections),
        "sections": [
            {"type": key, "heading": heading, "entries": entries}
            for key, heading, entries in sections
        ],
    }
    if filtered_count > 0:
        data["filtered_commits"] = filtered_count
    return _json.dumps(data, indent=2)
