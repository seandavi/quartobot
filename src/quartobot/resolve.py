"""Pre-fetch citations via manubot before render.

`quartobot resolve` runs `manubot.cite` against a list of persistent-
identifier cite keys (either passed as arguments or scanned out of a
project) and writes the resulting bibliography to disk. The point
isn't to replace what `pandoc-manubot-cite` does at render time — it's
to do the network work on a developer's machine, ahead of push, so CI
never sees a Crossref or PubMed hiccup.

Two artifacts are produced by default:

- ``references.resolved.bib`` — a BibLaTeX file pandoc consumes during
  render. This is the file ``_quarto.yml`` lists under
  ``bibliography:``. BibLaTeX is pandoc-citeproc's native bibliography
  format and is the only one Quarto's ``manuscript`` project type
  reads cleanly via its Google Scholar metadata post-process.
- ``references.json`` — CSL JSON for an internal cache. Next resolve
  reads this for cache hits and skips the network call.

Hand-curated cite keys (no recognized prefix) are filtered out: those
live in `references.bib` and pandoc citeproc handles them.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quartobot.scan import scan_path

STDOUT_SENTINEL = "-"
"""Output sentinel for streaming CSL JSON to stdout instead of a file."""

DEFAULT_BIB_OUTPUT = "references.resolved.bib"
"""Default filename for the BibLaTeX artifact pandoc reads at render."""

logger = logging.getLogger(__name__)

# A CSL JSON item (manubot's `csl_item` is dict-like with mixed types).
# Aliased here to keep type signatures readable without committing to a
# strict TypedDict — manubot's items vary by source.
CSLItem = dict[str, Any]


@dataclass(frozen=True)
class Resolution:
    """The outcome of resolving one cite key."""

    key: str
    """The input key as the user provided it (e.g. `doi:10.1371/foo`)."""
    standard_id: str
    """Manubot's canonical form (e.g. `doi:10.1371/foo`)."""
    short_id: str | None
    """Manubot's short hash used as CSL `id`. None if resolution failed."""
    succeeded: bool
    """Whether resolution produced a CSL item."""
    error: str | None = None
    """Error message when succeeded is False."""


@dataclass
class ResolveOutcome:
    """The aggregate outcome of a resolve run."""

    resolutions: list[Resolution] = field(default_factory=list)
    output_path: Path | None = None
    bib_output_path: Path | None = None
    """Where the BibLaTeX artifact was written. None if not written."""
    entries_written: int = 0
    cache_hits: int = 0
    wrote_stdout: bool = False
    """True when the resolved CSL JSON was streamed to stdout."""

    @property
    def failures(self) -> list[Resolution]:
        """Return only the failed resolutions."""
        return [r for r in self.resolutions if not r.succeeded]

    @property
    def successes(self) -> list[Resolution]:
        """Return only the successful resolutions."""
        return [r for r in self.resolutions if r.succeeded]


def collect_resolvable_keys(path: Path, *, recursive: bool = True) -> list[str]:
    """Walk `path` and return unique persistent-identifier cite keys.

    Hand-curated cite keys (no recognized prefix and not a bare-DOI form)
    are excluded — those belong in `references.bib` and pandoc citeproc
    handles them.

    Pass `recursive=False` to limit a directory scan to files directly
    under `path` (no descent).

    Keys are returned in their `prefix:identifier` (manubot-standard)
    form, without the leading `@`. Duplicates removed.
    """
    result = scan_path(path, recursive=recursive)
    seen: set[str] = set()
    out: list[str] = []
    for occ in result.occurrences:
        if occ.prefix is None:
            continue
        standard = f"{occ.prefix}:{occ.identifier}"
        if standard in seen:
            continue
        seen.add(standard)
        out.append(standard)
    return out


def _load_existing(path: Path | None) -> list[CSLItem]:
    """Read an existing CSL JSON file. Return empty list if missing."""
    if path is None or not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _standard_id_from_note(note: object) -> str | None:
    """Extract `standard_id: <value>` from manubot's `note` field."""
    if not isinstance(note, str):
        return None
    for line in note.splitlines():
        line = line.strip()
        if line.startswith("standard_id:"):
            return line.split(":", 1)[1].strip()
    return None


def _csljson_to_biblatex(csl_json_text: str) -> str:
    """Convert CSL JSON text to BibLaTeX via ``pandoc``.

    Pandoc converts CSL JSON to BibLaTeX cleanly in one shot and
    incidentally coerces field types along the way — date-parts strings
    become integer-typed dates, etc. — which sidesteps a class of bugs
    where manubot's URL-metadata resolver returns string years.

    Raises ``RuntimeError`` if ``pandoc`` isn't on PATH or fails.
    """
    pandoc = shutil.which("pandoc")
    if pandoc is None:
        raise RuntimeError(
            "pandoc not found on PATH. quartobot resolve needs pandoc to "
            "convert CSL JSON to BibLaTeX. Quarto bundles pandoc, but the "
            "pre-render hook runs in a subprocess that may not have it on "
            "PATH. Install pandoc (https://pandoc.org/installing.html) "
            "or ensure Quarto's bundled pandoc is exposed."
        )
    try:
        result = subprocess.run(
            [pandoc, "-f", "csljson", "-t", "biblatex"],
            input=csl_json_text,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"pandoc failed converting CSL JSON to BibLaTeX "
            f"(exit {exc.returncode}): {exc.stderr.strip()}"
        ) from exc
    return result.stdout


def _build_cache_index(items: Sequence[CSLItem]) -> dict[str, CSLItem]:
    """Index existing CSL items by their `standard_id` note.

    Manubot writes the standard_id into the CSL item's `note` field as
    `standard_id: <value>`. We parse that out to detect cache hits and
    avoid re-resolving keys we already have.
    """
    out: dict[str, CSLItem] = {}
    for item in items:
        sid = _standard_id_from_note(item.get("note", ""))
        if sid is not None:
            out[sid] = item
    return out


def resolve_keys(
    keys: Iterable[str],
    *,
    cache_path: Path | None = None,
    output_path: Path | str | None = None,
    bib_output_path: Path | str | None = None,
    dry_run: bool = False,
    log_level: str = "WARNING",
    id_mode: str = "short-hash",
) -> ResolveOutcome:
    """Resolve a list of persistent-identifier keys.

    Args:
        keys: Cite keys in `prefix:identifier` form (no leading `@`).
        cache_path: Optional path to read previously-resolved entries
            from. Cache hits skip the network call.
        output_path: Where to write the merged CSL JSON cache. A `Path`
            writes to that file. The string `"-"` writes to stdout (no
            file side effect). `None` skips writing entirely.
        bib_output_path: Where to write the BibLaTeX artifact that
            pandoc reads at render. A `Path` writes to that file.
            `None` (the default) skips the BibLaTeX write — used when
            ``output_path`` is the stdout sentinel or when the caller
            only wants the CSL JSON cache.
        dry_run: If True, don't make network calls — report what would
            be resolved.
        log_level: Manubot's logging verbosity for resolver failures.
        id_mode: How to populate the CSL `id` field in the output.
            "short-hash" (default) keeps manubot's hash form, which the
            `pandoc-manubot-cite` filter expects. "citation-key" writes
            the original `prefix:identifier` (e.g. `doi:10.1371/...`),
            which lets pandoc-citeproc match the prose keys directly
            without a filter — the pre-render-hook architecture.

    Returns:
        A `ResolveOutcome` describing what happened.
    """
    keys = list(keys)
    stdout_mode = output_path == STDOUT_SENTINEL
    # Anything that isn't the stdout sentinel or `None` is treated as a
    # filesystem path. Callers passing a plain string like "out.json"
    # used to silently no-op; coerce to Path so they get the write they
    # asked for.
    file_output: Path | None
    if stdout_mode or output_path is None:
        file_output = None
    elif isinstance(output_path, Path):
        file_output = output_path
    else:
        file_output = Path(output_path)
    outcome = ResolveOutcome(output_path=file_output)

    if dry_run:
        for k in keys:
            outcome.resolutions.append(
                Resolution(key=k, standard_id=k, short_id=None, succeeded=True)
            )
        return outcome

    # Defer the import so unit tests can monkey-patch without pulling
    # the whole manubot dependency tree at module-import time.
    from manubot.cite.citekey import CiteKey, citekey_to_csl_item

    existing = _load_existing(cache_path)
    cache_index = _build_cache_index(existing)
    # Output is the union of cache + new resolutions, keyed by short_id.
    new_items: dict[str, CSLItem] = {item["id"]: item for item in existing if "id" in item}

    for key in keys:
        try:
            ck = CiteKey(key, infer_prefix=True)
        except Exception as exc:
            outcome.resolutions.append(
                Resolution(
                    key=key,
                    standard_id=key,
                    short_id=None,
                    succeeded=False,
                    error=f"parse: {exc}",
                )
            )
            continue

        if ck.standard_id in cache_index:
            cached = cache_index[ck.standard_id]
            outcome.cache_hits += 1
            outcome.resolutions.append(
                Resolution(
                    key=key,
                    standard_id=ck.standard_id,
                    short_id=cached.get("id"),
                    succeeded=True,
                )
            )
            continue

        try:
            csl_item = citekey_to_csl_item(ck, log_level=log_level)
        except Exception as exc:
            outcome.resolutions.append(
                Resolution(
                    key=key,
                    standard_id=ck.standard_id,
                    short_id=None,
                    succeeded=False,
                    error=str(exc),
                )
            )
            continue

        if csl_item is None:
            outcome.resolutions.append(
                Resolution(
                    key=key,
                    standard_id=ck.standard_id,
                    short_id=None,
                    succeeded=False,
                    error="resolver returned None",
                )
            )
            continue

        # csl_item is a manubot CSL_Item (dict-like). Coerce to plain dict
        # for JSON serialization.
        plain = dict(csl_item)
        new_items[plain["id"]] = plain
        outcome.resolutions.append(
            Resolution(
                key=key,
                standard_id=ck.standard_id,
                short_id=plain.get("id"),
                succeeded=True,
            )
        )

    if (file_output is not None or stdout_mode) and not dry_run:
        merged = list(new_items.values())
        if id_mode == "citation-key":
            # Re-key each item to the citation key as it appears in the
            # prose, so pandoc-citeproc can match directly without an
            # AST-rewriting filter in the chain. Prefer the user's
            # input key (e.g. `pmid:`) over manubot's canonical form
            # (e.g. `pubmed:`) — they can differ, and the prose is the
            # source of truth for what citeproc will look for. Cached
            # entries with no matching resolution this run fall back to
            # the standard_id from manubot's `note` field.
            key_by_sid: dict[str, str] = {}
            for res in outcome.resolutions:
                if res.succeeded and res.standard_id and res.key:
                    key_by_sid.setdefault(res.standard_id, res.key)
            for item in merged:
                sid = _standard_id_from_note(item.get("note", ""))
                if sid is not None:
                    item["id"] = key_by_sid.get(sid, sid)
        # Sort by id for deterministic diffs.
        merged.sort(key=lambda d: d.get("id", ""))
        serialized = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
        if stdout_mode:
            sys.stdout.write(serialized)
            sys.stdout.flush()
            outcome.wrote_stdout = True
        else:
            assert file_output is not None  # narrowed by branch condition
            file_output.parent.mkdir(parents=True, exist_ok=True)
            file_output.write_text(serialized, encoding="utf-8")
        outcome.entries_written = len(merged)

        # BibLaTeX side-output. Skipped in stdout mode (the one-shot
        # piping use case) and when the caller hasn't asked for one.
        # Empty bibliographies don't go through pandoc — its csljson
        # reader rejects ``[]``.
        if bib_output_path is not None and not stdout_mode and merged:
            bib_path = (
                bib_output_path
                if isinstance(bib_output_path, Path)
                else Path(bib_output_path)
            )
            bibtex = _csljson_to_biblatex(serialized)
            bib_path.parent.mkdir(parents=True, exist_ok=True)
            bib_path.write_text(bibtex, encoding="utf-8")
            outcome.bib_output_path = bib_path

    return outcome


def format_outcome(outcome: ResolveOutcome) -> str:
    """Render a `ResolveOutcome` as the human-readable CLI report."""
    lines: list[str] = []
    if not outcome.resolutions:
        return "No persistent-identifier cite keys to resolve."

    for res in outcome.resolutions:
        if res.succeeded:
            short = f" → {res.short_id}" if res.short_id else " (dry-run)"
            lines.append(f"  ✓ {res.standard_id}{short}")
        else:
            lines.append(f"  ✗ {res.standard_id} — {res.error}")

    n_ok = len(outcome.successes)
    n_fail = len(outcome.failures)
    lines.append("")
    summary = f"{n_ok} resolved"
    if outcome.cache_hits:
        summary += f" ({outcome.cache_hits} from cache)"
    if n_fail:
        summary += f", {n_fail} failed"
    if outcome.wrote_stdout:
        summary += f". Wrote {outcome.entries_written} entries to stdout."
    elif outcome.bib_output_path is not None and outcome.output_path is not None:
        summary += (
            f". Wrote {outcome.entries_written} entries to "
            f"{outcome.bib_output_path} (BibLaTeX) and "
            f"{outcome.output_path} (CSL JSON cache)."
        )
    elif outcome.output_path is not None:
        summary += f". Wrote {outcome.entries_written} entries to {outcome.output_path}."
    lines.append(summary)
    return "\n".join(lines)


__all__: Sequence[str] = (
    "DEFAULT_BIB_OUTPUT",
    "Resolution",
    "ResolveOutcome",
    "collect_resolvable_keys",
    "format_outcome",
    "resolve_keys",
)
