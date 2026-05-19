"""Generate the ``/versions/`` page and its ``state.json`` file.

quartobot's optional manuscript-as-software layer deploys per-commit
permalinks at ``/v/<sha>/`` on gh-pages alongside the latest at root
and PR previews at ``/pr/<n>/``. Discoverability of those URLs is the
job of this module: it builds a ``/versions/`` page that lists tagged
releases, recent commits on main, and open PR previews, with a
``state.json`` companion that's the rebuildable source of truth.

This module is pure-function — input is the gh-pages inventory plus
git facts (latest sha, tag map, open PR list), output is a
:class:`VersionState` and an HTML page. No shelling out, no network.
The git facts get gathered by the caller (the CLI / GitHub Action)
and passed in.

Composition with :mod:`quartobot.snapshots`:

* ``snapshots.inventory(gh_pages_dir)`` enumerates what's on disk.
* :func:`derive_state` cross-references the inventory with the
  caller-supplied git facts to decide what shows up on the versions
  page. A sha that's on disk but doesn't appear in git (orphaned
  after a squash, for example) still gets listed — just without a
  commit title.
* :func:`render_html` formats the state as a static HTML page.

The HTML output is intentionally minimal: no JS, no client-side
fetch, inlined CSS, ~200 bytes per entry. The page is rebuildable
from gh-pages contents alone, so a corrupted ``state.json`` is
self-healing on the next render.
"""

from __future__ import annotations

import html
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from quartobot.snapshots import Inventory

SHORT_SHA_LEN = 7
STATE_FILE_RELPATH = "versions/state.json"
HTML_FILE_RELPATH = "versions/index.html"
STATE_VERSION = 1


# ──────────────────────────────────────────── caller-supplied facts


@dataclass(frozen=True)
class ShaInfo:
    """Display metadata for a git commit.

    Attributes:
        sha: Full 40-char commit sha.
        title: Commit message subject line, or ``None`` if the commit
            isn't reachable in the current checkout.
        date: ISO 8601 commit date, or ``None`` if unknown.
    """

    sha: str
    title: str | None = None
    date: str | None = None


@dataclass(frozen=True)
class TagInfo:
    """A git tag pointing at a sha.

    Attributes:
        sha: Full sha the tag points to.
        tag: Tag name (without ``refs/tags/`` prefix).
    """

    sha: str
    tag: str


@dataclass(frozen=True)
class PRInfo:
    """An open pull request with a deployed preview.

    Attributes:
        number: PR number.
        title: PR title.
        branch: Head ref (branch name).
        sha: Full sha of the head commit.
        date: ISO 8601 timestamp of the last update, or ``None``.
    """

    number: int
    title: str
    branch: str
    sha: str
    date: str | None = None


# ──────────────────────────────────────────── state model


@dataclass(frozen=True)
class VersionEntry:
    """A versioned snapshot deployed at ``/v/<sha>/``.

    Attributes:
        sha: Full sha, the directory name on gh-pages.
        short_sha: First 7 chars, for display.
        tag: Git tag at this sha, or ``None`` for untagged commits.
        date: ISO 8601 date — commit date if known, snapshot mtime
            otherwise.
        title: Commit message subject, or ``None`` if not available.
    """

    sha: str
    short_sha: str
    tag: str | None
    date: str
    title: str | None


@dataclass(frozen=True)
class PRPreview:
    """An open PR's preview deploy at ``/pr/<number>/``.

    Attributes:
        number: PR number.
        title: PR title.
        branch: Head ref name.
        sha: Latest head sha.
        short_sha: First 7 chars of ``sha``.
        date: ISO 8601 timestamp, or ``None``.
    """

    number: int
    title: str
    branch: str
    sha: str
    short_sha: str
    date: str | None


@dataclass(frozen=True)
class VersionState:
    """The full state of a quartobot-versioned gh-pages site.

    Attributes:
        latest_sha: Full sha currently served at ``/``, or ``None``
            if the site has never been deployed.
        entries: All retained snapshots (tagged + recent), ordered
            newest first by date.
        prs: Open PR previews, ordered by PR number ascending.
        generated_at: ISO 8601 timestamp of when this state was
            derived. Recorded in ``state.json`` for diff visibility.
        state_version: Schema version for ``state.json``; bumped
            on breaking format changes.
    """

    latest_sha: str | None
    entries: tuple[VersionEntry, ...]
    prs: tuple[PRPreview, ...]
    generated_at: str
    state_version: int = STATE_VERSION


# ──────────────────────────────────────────── state derivation


def derive_state(
    inventory: Inventory,
    *,
    latest_sha: str | None,
    sha_info: dict[str, ShaInfo] | None = None,
    tag_info: Iterable[TagInfo] = (),
    open_prs: Iterable[PRInfo] = (),
    now: datetime | None = None,
) -> VersionState:
    """Build a :class:`VersionState` from disk inventory and git facts.

    The returned state lists only entries that are *both* on disk and
    plausible — i.e., the sha shows up in the gh-pages inventory's
    ``v/`` directory. A tag pointing at a sha that isn't deployed is
    silently dropped: tags reflect git, but versions reflect what
    readers can actually click on.

    PRs are filtered the same way: a PR in ``open_prs`` that doesn't
    have a ``pr/<number>/`` directory on disk is dropped (preview not
    yet deployed). A ``pr/<number>/`` directory on disk that isn't in
    ``open_prs`` is also dropped (PR closed; cleanup workflow
    pending).

    Args:
        inventory: Result of :func:`snapshots.inventory`.
        latest_sha: The sha currently served at root.
        sha_info: Optional commit-display metadata keyed by full sha.
            Entries with no matching info still appear, but without
            title or commit-date enrichment.
        tag_info: All known git tags. Tags pointing at undeployed
            shas are ignored.
        open_prs: PRs currently open in the repo.
        now: Override for ``generated_at`` (testing).

    Returns:
        The derived state, with entries newest-first and PRs ordered
        by number.
    """
    sha_info = sha_info or {}
    tag_by_sha: dict[str, str] = {t.sha: t.tag for t in tag_info}
    pr_by_number: dict[int, PRInfo] = {p.number: p for p in open_prs}

    entries: list[VersionEntry] = []
    for snap in inventory.snapshots:
        sha_meta = sha_info.get(snap.sha)
        # Commit date wins if known; otherwise the snapshot's mtime
        # is the best signal we have for "when this version exists."
        if sha_meta and sha_meta.date:
            date_str = sha_meta.date
        else:
            date_str = (
                datetime.fromtimestamp(snap.mtime, tz=timezone.utc).date().isoformat()
            )
        entries.append(
            VersionEntry(
                sha=snap.sha,
                short_sha=snap.sha[:SHORT_SHA_LEN],
                tag=tag_by_sha.get(snap.sha),
                date=date_str,
                title=sha_meta.title if sha_meta else None,
            )
        )
    # Newest first. Use date string compare (ISO-8601 sorts lexically).
    entries.sort(key=lambda e: e.date, reverse=True)

    prs: list[PRPreview] = []
    for pr_dir in sorted(inventory.pr_dirs.keys(), key=_pr_dir_sort_key):
        try:
            number = int(pr_dir)
        except ValueError:
            # Non-numeric directory under pr/ — skip rather than crash.
            continue
        pr_meta = pr_by_number.get(number)
        if pr_meta is None:
            # Stale preview directory for a PR that's no longer open;
            # don't surface it on the versions page even though the
            # directory survives until pr-closed.yml runs.
            continue
        prs.append(
            PRPreview(
                number=pr_meta.number,
                title=pr_meta.title,
                branch=pr_meta.branch,
                sha=pr_meta.sha,
                short_sha=pr_meta.sha[:SHORT_SHA_LEN],
                date=pr_meta.date,
            )
        )

    if now is None:
        now = datetime.now(tz=timezone.utc)
    return VersionState(
        latest_sha=latest_sha,
        entries=tuple(entries),
        prs=tuple(prs),
        generated_at=now.isoformat(timespec="seconds"),
    )


def _pr_dir_sort_key(name: str) -> tuple[int, int | str]:
    """Numeric PR dirs sort numerically; anything else falls last."""
    try:
        return (0, int(name))
    except ValueError:
        return (1, name)


# ──────────────────────────────────────────── IO


def load_state(gh_pages_dir: Path) -> VersionState | None:
    """Read ``state.json`` from ``gh_pages_dir/versions/``.

    Returns ``None`` if the file is absent or its schema version is
    older than this module knows about. The caller should fall back
    to re-deriving from inventory when this returns ``None``.

    Args:
        gh_pages_dir: Path to a gh-pages tree.

    Returns:
        The loaded state, or ``None`` if absent / incompatible.

    Raises:
        json.JSONDecodeError: If the file is present but malformed.
            The caller should treat this as a hard error rather than
            silently fall back — corruption shouldn't be hidden.
    """
    path = gh_pages_dir / STATE_FILE_RELPATH
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("state_version") != STATE_VERSION:
        return None
    return VersionState(
        latest_sha=raw.get("latest_sha"),
        entries=tuple(VersionEntry(**e) for e in raw.get("entries", ())),
        prs=tuple(PRPreview(**p) for p in raw.get("prs", ())),
        generated_at=raw["generated_at"],
        state_version=raw["state_version"],
    )


def save_state(state: VersionState, gh_pages_dir: Path) -> Path:
    """Write ``state.json`` to ``gh_pages_dir/versions/``.

    Creates the ``versions/`` directory if needed. Pretty-prints the
    JSON so diffs on gh-pages are readable.

    Args:
        state: The state to serialize.
        gh_pages_dir: Path to the gh-pages tree.

    Returns:
        Absolute path to the written file.
    """
    path = gh_pages_dir / STATE_FILE_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(state), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def write_page(
    state: VersionState,
    gh_pages_dir: Path,
    *,
    project_title: str = "manuscript",
) -> tuple[Path, Path]:
    """Write both ``state.json`` and ``versions/index.html``.

    Args:
        state: State to render.
        gh_pages_dir: Path to the gh-pages tree.
        project_title: Title for the HTML ``<h1>`` and ``<title>``.

    Returns:
        ``(state_path, html_path)`` — the absolute paths written.
    """
    state_path = save_state(state, gh_pages_dir)
    html_path = gh_pages_dir / HTML_FILE_RELPATH
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(state, project_title=project_title), encoding="utf-8")
    return state_path, html_path


# ──────────────────────────────────────────── HTML render


_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
       max-width: 50em; margin: 2em auto; padding: 0 1em; color: #1a1a1a;
       line-height: 1.5; }
h1 { font-size: 1.6em; margin-bottom: 0.2em; }
h2 { font-size: 1.15em; margin-top: 2em; padding-top: 0.5em;
     border-top: 1px solid #ddd; }
ul { list-style: none; padding: 0; }
li { margin: 0.5em 0; padding: 0.5em 0; border-bottom: 1px solid #f0f0f0; }
li:last-child { border-bottom: none; }
.tag { font-weight: 600; color: #006400; margin-right: 0.4em; }
.sha { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 0.9em; }
.date { color: #666; font-size: 0.9em; margin-left: 0.4em; }
.title { display: block; color: #444; margin-top: 0.2em; font-size: 0.95em; }
.pr-number { font-weight: 600; }
.pr-branch { font-family: ui-monospace, monospace; font-size: 0.85em; color: #666; }
.empty { color: #888; font-style: italic; }
footer { margin-top: 3em; padding-top: 1em; border-top: 1px solid #ddd;
         font-size: 0.85em; color: #888; }
a { color: #0066cc; }
a:hover { text-decoration: underline; }
"""


def render_html(state: VersionState, *, project_title: str = "manuscript") -> str:
    """Format a :class:`VersionState` as a standalone HTML page.

    Output is self-contained: inlined CSS, no JS, no external assets.
    Safe to deploy at ``/versions/index.html`` on any static host.

    Args:
        state: State to render.
        project_title: Title shown in ``<h1>`` and ``<title>``.

    Returns:
        A complete HTML document as a string.
    """
    title = html.escape(project_title)
    tagged = [e for e in state.entries if e.tag is not None]
    untagged = [e for e in state.entries if e.tag is None]

    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en">')
    parts.append("<head>")
    parts.append('<meta charset="UTF-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    parts.append(f"<title>Versions — {title}</title>")
    parts.append(f"<style>{_CSS}</style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append("<main>")
    parts.append(f"<h1>{title}: versions</h1>")

    parts.append("<h2>Latest</h2>")
    if state.latest_sha:
        short = html.escape(state.latest_sha[:SHORT_SHA_LEN])
        parts.append(
            f'<p><a href="/">latest</a> '
            f'<span class="sha">(commit {short})</span></p>'
        )
    else:
        parts.append('<p class="empty">No deploys yet.</p>')

    parts.append("<h2>Tagged releases</h2>")
    if tagged:
        parts.append("<ul>")
        for e in tagged:
            parts.append(_render_entry(e))
        parts.append("</ul>")
    else:
        parts.append('<p class="empty">No tagged releases yet.</p>')

    parts.append("<h2>Recent commits on main</h2>")
    if untagged:
        parts.append("<ul>")
        for e in untagged:
            parts.append(_render_entry(e))
        parts.append("</ul>")
    else:
        parts.append('<p class="empty">No untagged snapshots retained.</p>')

    parts.append("<h2>Open PR previews</h2>")
    if state.prs:
        parts.append("<ul>")
        for pr in state.prs:
            parts.append(_render_pr(pr))
        parts.append("</ul>")
    else:
        parts.append('<p class="empty">No open PRs with preview deploys.</p>')

    parts.append("<footer>")
    parts.append(
        f'<p>Generated {html.escape(state.generated_at)} by '
        f'<a href="https://quartobot.github.io/quartobot/">quartobot</a>.</p>'
    )
    parts.append("</footer>")
    parts.append("</main>")
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts) + "\n"


def _render_entry(e: VersionEntry) -> str:
    """Render a single :class:`VersionEntry` as an ``<li>``."""
    tag = (
        f'<span class="tag">{html.escape(e.tag)}</span>'
        if e.tag
        else ""
    )
    title = (
        f'<span class="title">{html.escape(e.title)}</span>'
        if e.title
        else ""
    )
    return (
        f"<li>"
        f'{tag}'
        f'<a class="sha" href="/v/{html.escape(e.sha)}/">{html.escape(e.short_sha)}</a>'
        f'<span class="date">{html.escape(e.date)}</span>'
        f"{title}"
        f"</li>"
    )


def _render_pr(pr: PRPreview) -> str:
    """Render a single :class:`PRPreview` as an ``<li>``."""
    date_span = (
        f'<span class="date">{html.escape(pr.date)}</span>'
        if pr.date
        else ""
    )
    return (
        f"<li>"
        f'<span class="pr-number">PR #{pr.number}</span> '
        f'<a href="/pr/{pr.number}/">{html.escape(pr.title)}</a> '
        f'<span class="pr-branch">{html.escape(pr.branch)}</span>'
        f'{date_span}'
        f"</li>"
    )


__all__ = [
    "HTML_FILE_RELPATH",
    "STATE_FILE_RELPATH",
    "STATE_VERSION",
    "PRInfo",
    "PRPreview",
    "ShaInfo",
    "TagInfo",
    "VersionEntry",
    "VersionState",
    "derive_state",
    "load_state",
    "render_html",
    "save_state",
    "write_page",
]
