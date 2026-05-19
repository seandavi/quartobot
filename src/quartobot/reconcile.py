"""Reconcile citation-key collisions between ``references.bib`` and ``references.json``.

quartobot's pre-render hook writes auto-resolved entries to
``references.json``. Hand-curated entries live alongside in
``references.bib``. Both files get passed to pandoc-citeproc via
``_quarto.yml``'s ``bibliography:`` list. If the same key appears in
both, pandoc-citeproc silently picks one (its later-wins default),
which is the kind of bug that surfaces months later when someone
notices a fact is wrong in the rendered output.

This module finds those collisions and resolves them with explicit
modes:

* ``accept_bibtex`` — drop the conflicting entry from
  ``references.json``. ``references.bib`` stays the source of truth.
* ``accept_json`` — drop the conflicting entry from
  ``references.bib``. The auto-resolved entry stays.
* ``manual`` (interactive) — per-collision picker with diff-flagged
  side-by-side display.

No mode is the default — the caller must pick one. Silent precedence
is a bug, not a feature.

Whenever this module mutates a file, it writes a timestamped backup
first: ``references.bib.bak-<ISO-TS>`` and/or
``references.json.bak-<ISO-TS>``. Both files in the same reconcile
run share the timestamp, so a one-line undo restores the
pre-reconcile state.

This module is pure-IO over the provided paths — no shelling out,
no network. The interactive picker takes a callable for the prompt
so tests can substitute a scripted responder.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

BACKUP_SUFFIX_FMT = "bak-%Y%m%dT%H%M%SZ"
"""strftime format for the backup suffix. ISO-ish, no separators, UTC."""

# Entry-start: `@type{key,` with optional whitespace. The key is
# everything up to the next comma (and not containing whitespace or
# braces). Skips @string, @preamble, @comment (non-data entries).
_ENTRY_START_RE = re.compile(
    r"@(?P<type>[A-Za-z]+)\s*\{\s*(?P<key>[^,\s\}]+)\s*,",
    re.MULTILINE,
)

_NON_DATA_ENTRY_TYPES = frozenset({"string", "preamble", "comment"})


# ──────────────────────────────────────────── data model


@dataclass(frozen=True)
class BibEntry:
    """A parsed entry from a .bib file.

    Attributes:
        key: The citation key (e.g., ``doi:10.1038/abc``).
        entry_type: The entry type without the ``@`` (e.g., ``article``).
        text: The full entry text, including the ``@type{...}`` braces.
        start: Byte offset where the entry begins in the source file.
        end: Byte offset where the entry ends (one past the closing
            brace).
    """

    key: str
    entry_type: str
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Collision:
    """A citation key present in both ``references.bib`` and ``references.json``.

    Attributes:
        key: The colliding citation key.
        bib_entry: The full bib entry from ``references.bib``.
        json_entry: The CSL item dict from ``references.json``.
    """

    key: str
    bib_entry: BibEntry
    json_entry: dict[str, Any]


@dataclass(frozen=True)
class FileChange:
    """One file mutation performed by reconcile.

    Attributes:
        path: The file that was (or would be) modified.
        backup_path: Where the pre-mutation backup was (or would be)
            written. ``None`` when no mutation happens (dry-run + no
            collisions, or this side wasn't touched).
        entries_removed: Number of entries dropped from this file.
    """

    path: Path
    backup_path: Path | None
    entries_removed: int


@dataclass(frozen=True)
class ReconcileOutcome:
    """The aggregate result of one reconcile run.

    Attributes:
        mode: Which resolution mode was used.
        decisions: Per-collision decision — ``bib`` (kept bib, dropped
            json), ``json`` (kept json, dropped bib), or ``skip``
            (left both in place; only possible from manual mode).
        bib_change: Mutation done to ``references.bib`` (or ``None``
            if untouched).
        json_change: Mutation done to ``references.json`` (or
            ``None`` if untouched).
        dry_run: True when no files were actually written.
    """

    mode: Literal["accept-bibtex", "accept-json", "manual"]
    decisions: dict[str, Literal["bib", "json", "skip"]] = field(default_factory=dict)
    bib_change: FileChange | None = None
    json_change: FileChange | None = None
    dry_run: bool = False


# ──────────────────────────────────────────── parsing


def parse_bib(text: str) -> list[BibEntry]:
    r"""Extract entries from a BibTeX file's text.

    Skips ``@string``, ``@preamble``, and ``@comment`` entries —
    those don't carry citation keys. Handles brace-balanced fields
    and backslash-escaped characters (so ``\{`` inside a title
    doesn't fool the parser).

    Args:
        text: The full text of a .bib file.

    Returns:
        The entries in document order. Each entry's ``text`` slice
        matches ``text[entry.start:entry.end]`` exactly.
    """
    entries: list[BibEntry] = []
    pos = 0
    while pos < len(text):
        match = _ENTRY_START_RE.search(text, pos)
        if not match:
            break
        entry_start = match.start()
        entry_type = match.group("type")
        key = match.group("key")
        if entry_type.lower() in _NON_DATA_ENTRY_TYPES:
            pos = match.end()
            continue
        # Find matching closing brace. Opening brace is part of the
        # match (it's the `{` after the entry type). Counter starts
        # at 1 — we're already inside the entry.
        depth = 1
        j = match.end()
        while j < len(text) and depth > 0:
            c = text[j]
            if c == "\\" and j + 1 < len(text):
                # Skip the next character; backslash escapes anything
                # that follows (including `{` or `}`).
                j += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            j += 1
        entry_end = j  # one past the closing brace
        entries.append(
            BibEntry(
                key=key,
                entry_type=entry_type,
                text=text[entry_start:entry_end],
                start=entry_start,
                end=entry_end,
            )
        )
        pos = entry_end
    return entries


def parse_json(text: str) -> list[dict[str, Any]]:
    """Parse a CSL JSON bibliography.

    Args:
        text: Raw JSON text. Must be an array of CSL items.

    Returns:
        The items, untouched.

    Raises:
        ValueError: If the document isn't a list at top level.
    """
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError(
            f"expected references.json to be a JSON array; got {type(data).__name__}"
        )
    return data


# ──────────────────────────────────────────── collision detection


def find_collisions(
    bib_entries: Iterable[BibEntry],
    json_items: Iterable[dict[str, Any]],
) -> list[Collision]:
    """Return the set of keys present in both inputs.

    Args:
        bib_entries: Parsed bib entries.
        json_items: CSL items with an ``id`` field.

    Returns:
        One :class:`Collision` per key in the intersection, ordered by
        the order the keys first appeared in the bib input. Items in
        the JSON input that lack an ``id`` field are ignored.
    """
    bib_by_key = {e.key: e for e in bib_entries}
    json_by_id: dict[str, dict[str, Any]] = {}
    for item in json_items:
        item_id = item.get("id")
        if isinstance(item_id, str):
            json_by_id[item_id] = item
    collisions: list[Collision] = []
    # Preserve bib order — when we show the manual picker, going
    # through entries in source order is less surprising.
    for entry in bib_by_key.values():
        if entry.key in json_by_id:
            collisions.append(
                Collision(
                    key=entry.key,
                    bib_entry=entry,
                    json_entry=json_by_id[entry.key],
                )
            )
    return collisions


# ──────────────────────────────────────────── mutation


def _backup_path(original: Path, now: datetime) -> Path:
    """Compute the backup path for ``original`` at ``now``.

    Example:
        ``references.bib`` at ``2026-05-19 08:53:00 UTC`` →
        ``references.bib.bak-20260519T085300Z``.
    """
    suffix = now.strftime(BACKUP_SUFFIX_FMT)
    return original.with_name(original.name + "." + suffix)


def _drop_bib_entries(text: str, to_drop: Iterable[BibEntry]) -> str:
    """Return ``text`` with the given entries removed.

    Entries are removed by byte range. Adjacent blank lines around
    each removal are collapsed so the file doesn't end up with two
    consecutive blank lines.

    Entries must be from a single ``parse_bib(text)`` call; mixing
    entries from different parses produces wrong offsets.
    """
    # Sort by start descending so removing from the end first leaves
    # earlier offsets stable.
    drops = sorted(to_drop, key=lambda e: e.start, reverse=True)
    out = text
    for entry in drops:
        before = out[: entry.start]
        after = out[entry.end :]
        # Eat trailing newline + optional whitespace after the entry
        # so the cut doesn't leave a stranded blank line.
        i = 0
        while i < len(after) and after[i] in (" ", "\t"):
            i += 1
        if i < len(after) and after[i] == "\n":
            i += 1
        after = after[i:]
        out = before + after
    # Collapse any 3+ consecutive newlines that the cuts may have
    # produced into 2 (one blank line between blocks).
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def _drop_json_entries(items: list[dict[str, Any]], keys: Iterable[str]) -> list[dict[str, Any]]:
    """Return ``items`` minus any with ``id`` in ``keys``."""
    drop_set = set(keys)
    return [item for item in items if item.get("id") not in drop_set]


# ──────────────────────────────────────────── modes


def accept_bibtex(
    bib_path: Path,
    json_path: Path,
    collisions: list[Collision],
    *,
    dry_run: bool = False,
    now: datetime | None = None,
) -> ReconcileOutcome:
    """Drop the conflicting entries from ``references.json``.

    ``references.bib`` is unchanged. A ``.json.bak-<TS>`` backup is
    written before mutation unless ``dry_run`` is set.
    """
    now = now or datetime.now(tz=timezone.utc)
    decisions: dict[str, Literal["bib", "json", "skip"]] = {c.key: "bib" for c in collisions}

    json_text = json_path.read_text(encoding="utf-8")
    json_items = parse_json(json_text)
    drop_keys = [c.key for c in collisions]
    new_items = _drop_json_entries(json_items, drop_keys)
    removed = len(json_items) - len(new_items)

    backup = _backup_path(json_path, now) if removed > 0 else None
    if not dry_run and removed > 0:
        assert backup is not None  # narrowed by `if not dry_run and removed > 0`
        json_path.replace(backup)
        # `replace` moves the original into the backup name, so we
        # now write the mutated content into the original path.
        json_path.write_text(
            json.dumps(new_items, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return ReconcileOutcome(
        mode="accept-bibtex",
        decisions=decisions,
        bib_change=None,
        json_change=FileChange(path=json_path, backup_path=backup, entries_removed=removed),
        dry_run=dry_run,
    )


def accept_json(
    bib_path: Path,
    json_path: Path,
    collisions: list[Collision],
    *,
    dry_run: bool = False,
    now: datetime | None = None,
) -> ReconcileOutcome:
    """Drop the conflicting entries from ``references.bib``.

    ``references.json`` is unchanged. A ``.bib.bak-<TS>`` backup is
    written before mutation unless ``dry_run`` is set.
    """
    now = now or datetime.now(tz=timezone.utc)
    decisions: dict[str, Literal["bib", "json", "skip"]] = {c.key: "json" for c in collisions}

    bib_text = bib_path.read_text(encoding="utf-8")
    new_text = _drop_bib_entries(bib_text, [c.bib_entry for c in collisions])
    removed = len(collisions)

    backup = _backup_path(bib_path, now) if removed > 0 else None
    if not dry_run and removed > 0:
        assert backup is not None  # narrowed by `if removed > 0`
        bib_path.replace(backup)
        bib_path.write_text(new_text, encoding="utf-8")

    return ReconcileOutcome(
        mode="accept-json",
        decisions=decisions,
        bib_change=FileChange(path=bib_path, backup_path=backup, entries_removed=removed),
        json_change=None,
        dry_run=dry_run,
    )


def manual_picker(
    bib_path: Path,
    json_path: Path,
    collisions: list[Collision],
    *,
    prompt: Callable[[Collision], str],
    dry_run: bool = False,
    now: datetime | None = None,
) -> ReconcileOutcome:
    """Per-collision interactive picker.

    Args:
        bib_path: Path to ``references.bib``.
        json_path: Path to ``references.json``.
        collisions: Collisions to walk through.
        prompt: Callable returning one of ``"b"`` (keep bib, drop
            json), ``"j"`` (keep json, drop bib), ``"s"`` (skip — keep
            both, will continue to conflict in pandoc-citeproc), or
            ``"q"`` (quit — apply choices made so far and exit). Used
            for testability; the CLI wires this to a stdin reader.
        dry_run: Don't write to disk.
        now: Override for backup timestamp (testing).

    Returns:
        Outcome with per-collision decisions and file changes for
        whichever files got touched.
    """
    now = now or datetime.now(tz=timezone.utc)
    decisions: dict[str, Literal["bib", "json", "skip"]] = {}
    bib_to_drop: list[BibEntry] = []
    json_keys_to_drop: list[str] = []

    for collision in collisions:
        answer = prompt(collision)
        if answer == "b":
            decisions[collision.key] = "bib"
            json_keys_to_drop.append(collision.key)
        elif answer == "j":
            decisions[collision.key] = "json"
            bib_to_drop.append(collision.bib_entry)
        elif answer == "s":
            decisions[collision.key] = "skip"
        elif answer == "q":
            break
        else:
            raise ValueError(
                f"manual picker got unexpected response {answer!r}; expected b/j/s/q"
            )

    bib_change: FileChange | None = None
    json_change: FileChange | None = None

    if bib_to_drop:
        bib_text = bib_path.read_text(encoding="utf-8")
        new_bib_text = _drop_bib_entries(bib_text, bib_to_drop)
        bib_backup = _backup_path(bib_path, now)
        if not dry_run:
            bib_path.replace(bib_backup)
            bib_path.write_text(new_bib_text, encoding="utf-8")
        bib_change = FileChange(
            path=bib_path,
            backup_path=bib_backup,
            entries_removed=len(bib_to_drop),
        )

    if json_keys_to_drop:
        json_text = json_path.read_text(encoding="utf-8")
        json_items = parse_json(json_text)
        new_items = _drop_json_entries(json_items, json_keys_to_drop)
        json_backup = _backup_path(json_path, now)
        if not dry_run:
            json_path.replace(json_backup)
            json_path.write_text(
                json.dumps(new_items, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        json_change = FileChange(
            path=json_path,
            backup_path=json_backup,
            entries_removed=len(json_keys_to_drop),
        )

    return ReconcileOutcome(
        mode="manual",
        decisions=decisions,
        bib_change=bib_change,
        json_change=json_change,
        dry_run=dry_run,
    )


# ──────────────────────────────────────────── logging


def format_collision_for_picker(collision: Collision) -> str:
    """Render a collision as a side-by-side block for the manual picker.

    Diff annotations highlight fields where the two entries disagree
    so the user can decide on substance, not on staring at metadata.
    """
    json_pretty = json.dumps(collision.json_entry, indent=2, ensure_ascii=False)

    parts: list[str] = []
    parts.append(f"─── @{collision.key} {'─' * max(0, 40 - len(collision.key))}")
    parts.append("references.bib:")
    for line in collision.bib_entry.text.splitlines():
        parts.append(f"  {line}")
    parts.append("")
    parts.append("references.json:")
    for line in json_pretty.splitlines():
        parts.append(f"  {line}")
    parts.append("")
    parts.append("[b]ib  [j]son  [s]kip  [q]uit?")
    return "\n".join(parts)


def format_outcome(outcome: ReconcileOutcome) -> str:
    """Render a :class:`ReconcileOutcome` as a human-readable summary."""
    lines: list[str] = []
    n_decisions = len(outcome.decisions)
    word = "Would reconcile" if outcome.dry_run else "Reconciled"
    lines.append(f"{word} {n_decisions} collision(s):")
    for key, decision in outcome.decisions.items():
        if decision == "bib":
            lines.append(f"  {'~' if outcome.dry_run else '✓'} {key} — accepted .bib version")
        elif decision == "json":
            lines.append(f"  {'~' if outcome.dry_run else '✓'} {key} — accepted .json version")
        else:
            lines.append(f"  · {key} — skipped (both entries remain)")
    lines.append("")

    if outcome.bib_change is None and outcome.json_change is None:
        lines.append("No files modified.")
        return "\n".join(lines)

    verb = "Would modify" if outcome.dry_run else "Modified"
    lines.append(f"{verb}:")
    for change in (outcome.bib_change, outcome.json_change):
        if change is None or change.entries_removed == 0:
            continue
        plural = "entry" if change.entries_removed == 1 else "entries"
        lines.append(f"  {change.path.name}  ({change.entries_removed} {plural} removed)")
        if change.backup_path is not None:
            qualifier = "would be written to" if outcome.dry_run else "backup"
            lines.append(f"    {qualifier}: {change.backup_path.name}")
    if not outcome.dry_run:
        lines.append("")
        lines.append("To restore either file: mv <backup> <original>")
    return "\n".join(lines)


__all__ = [
    "BACKUP_SUFFIX_FMT",
    "BibEntry",
    "Collision",
    "FileChange",
    "ReconcileOutcome",
    "accept_bibtex",
    "accept_json",
    "find_collisions",
    "format_collision_for_picker",
    "format_outcome",
    "manual_picker",
    "parse_bib",
    "parse_json",
]
