"""Tests for quartobot.versions — state derivation, IO, HTML render."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from quartobot.snapshots import Inventory, Snapshot
from quartobot.versions import (
    HTML_FILE_RELPATH,
    STATE_FILE_RELPATH,
    STATE_VERSION,
    PRInfo,
    PRPreview,
    ShaInfo,
    TagInfo,
    VersionEntry,
    VersionState,
    derive_state,
    load_state,
    render_html,
    save_state,
    write_page,
)

FIXED_NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
SHA_D = "d" * 40


def _inv(
    snapshots: tuple[Snapshot, ...] = (),
    pr_dirs: dict[str, int] | None = None,
    tmp_path: Path | None = None,
) -> Inventory:
    return Inventory(
        gh_pages_dir=tmp_path or Path("/dummy"),
        snapshots=snapshots,
        pr_dirs=pr_dirs or {},
        root_bytes=0,
        other_bytes=0,
    )


# ──────────────────────────────────────────── derive_state


def test_empty_inventory_produces_empty_state() -> None:
    state = derive_state(_inv(), latest_sha=None, now=FIXED_NOW)
    assert state.latest_sha is None
    assert state.entries == ()
    assert state.prs == ()
    assert state.state_version == STATE_VERSION
    assert state.generated_at == FIXED_NOW.isoformat(timespec="seconds")


def test_snapshot_without_git_info_uses_mtime_date() -> None:
    # mtime: 2026-04-01 00:00 UTC
    snap = Snapshot(sha=SHA_A, size_bytes=100, mtime=1_780_000_000.0)
    state = derive_state(_inv((snap,)), latest_sha=SHA_A, now=FIXED_NOW)
    assert len(state.entries) == 1
    entry = state.entries[0]
    assert entry.sha == SHA_A
    assert entry.short_sha == "aaaaaaa"
    assert entry.tag is None
    assert entry.title is None
    # mtime in UTC date form
    assert entry.date == "2026-05-28"


def test_snapshot_with_sha_info_uses_commit_date_and_title() -> None:
    snap = Snapshot(sha=SHA_A, size_bytes=100, mtime=1_780_000_000.0)
    info = {SHA_A: ShaInfo(sha=SHA_A, title="Add new figure", date="2026-04-10")}
    state = derive_state(_inv((snap,)), latest_sha=SHA_A, sha_info=info, now=FIXED_NOW)
    entry = state.entries[0]
    assert entry.title == "Add new figure"
    assert entry.date == "2026-04-10"


def test_tag_at_snapshot_sha_marks_entry_as_tagged() -> None:
    snap = Snapshot(sha=SHA_A, size_bytes=100, mtime=1_780_000_000.0)
    tags = [TagInfo(sha=SHA_A, tag="v1.0.0")]
    state = derive_state(_inv((snap,)), latest_sha=SHA_A, tag_info=tags, now=FIXED_NOW)
    assert state.entries[0].tag == "v1.0.0"


def test_tag_at_undeployed_sha_is_silently_dropped() -> None:
    snap = Snapshot(sha=SHA_A, size_bytes=100, mtime=1_780_000_000.0)
    tags = [
        TagInfo(sha=SHA_A, tag="v1.0.0"),
        TagInfo(sha=SHA_B, tag="v0.5.0"),  # not in inventory
    ]
    state = derive_state(_inv((snap,)), latest_sha=SHA_A, tag_info=tags, now=FIXED_NOW)
    assert [e.tag for e in state.entries] == ["v1.0.0"]


def test_entries_ordered_newest_first() -> None:
    older = Snapshot(sha=SHA_A, size_bytes=100, mtime=1_700_000_000.0)
    newer = Snapshot(sha=SHA_B, size_bytes=100, mtime=1_780_000_000.0)
    state = derive_state(_inv((older, newer)), latest_sha=SHA_B, now=FIXED_NOW)
    assert [e.sha for e in state.entries] == [SHA_B, SHA_A]


def test_pr_in_inventory_and_open_is_listed() -> None:
    pr_info = PRInfo(number=42, title="Fix abstract", branch="fix-abstract", sha=SHA_C)
    state = derive_state(
        _inv(pr_dirs={"42": 100}),
        latest_sha=None,
        open_prs=[pr_info],
        now=FIXED_NOW,
    )
    assert len(state.prs) == 1
    pr = state.prs[0]
    assert pr.number == 42
    assert pr.title == "Fix abstract"
    assert pr.branch == "fix-abstract"
    assert pr.sha == SHA_C
    assert pr.short_sha == "ccccccc"


def test_pr_dir_on_disk_but_no_open_pr_is_dropped() -> None:
    # Stale preview directory — PR closed, pr-closed.yml hasn't run yet.
    state = derive_state(
        _inv(pr_dirs={"99": 100}),
        latest_sha=None,
        open_prs=[],
        now=FIXED_NOW,
    )
    assert state.prs == ()


def test_open_pr_without_preview_dir_is_dropped() -> None:
    # PR is open but the preview hasn't been deployed yet (first build still running).
    pr_info = PRInfo(number=42, title="x", branch="x", sha=SHA_C)
    state = derive_state(
        _inv(pr_dirs={}),
        latest_sha=None,
        open_prs=[pr_info],
        now=FIXED_NOW,
    )
    assert state.prs == ()


def test_non_numeric_pr_dir_is_skipped() -> None:
    # Defensive — gh-pages shouldn't have non-numeric dirs under pr/
    # but we don't want to crash if it does.
    state = derive_state(
        _inv(pr_dirs={"abc": 100, "42": 200}),
        latest_sha=None,
        open_prs=[PRInfo(number=42, title="x", branch="x", sha=SHA_C)],
        now=FIXED_NOW,
    )
    assert [p.number for p in state.prs] == [42]


def test_prs_ordered_by_number_ascending() -> None:
    prs = [
        PRInfo(number=99, title="z", branch="z", sha=SHA_A),
        PRInfo(number=10, title="a", branch="a", sha=SHA_B),
        PRInfo(number=42, title="m", branch="m", sha=SHA_C),
    ]
    state = derive_state(
        _inv(pr_dirs={"10": 1, "42": 1, "99": 1}),
        latest_sha=None,
        open_prs=prs,
        now=FIXED_NOW,
    )
    assert [p.number for p in state.prs] == [10, 42, 99]


# ──────────────────────────────────────────── IO


def test_save_then_load_state_roundtrip(tmp_path: Path) -> None:
    state = VersionState(
        latest_sha=SHA_A,
        entries=(
            VersionEntry(
                sha=SHA_A,
                short_sha=SHA_A[:7],
                tag="v1.0",
                date="2026-04-10",
                title="Release",
            ),
        ),
        prs=(
            PRPreview(
                number=42,
                title="fix",
                branch="b",
                sha=SHA_B,
                short_sha=SHA_B[:7],
                date="2026-05-01",
            ),
        ),
        generated_at="2026-05-19T12:00:00+00:00",
    )
    save_state(state, tmp_path)
    assert (tmp_path / STATE_FILE_RELPATH).exists()
    loaded = load_state(tmp_path)
    assert loaded == state


def test_load_state_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_state(tmp_path) is None


def test_load_state_with_unknown_version_returns_none(tmp_path: Path) -> None:
    target = tmp_path / STATE_FILE_RELPATH
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "state_version": STATE_VERSION + 99,
                "latest_sha": None,
                "entries": [],
                "prs": [],
                "generated_at": "2026-05-19T12:00:00+00:00",
            }
        )
    )
    assert load_state(tmp_path) is None


def test_load_state_malformed_json_raises(tmp_path: Path) -> None:
    target = tmp_path / STATE_FILE_RELPATH
    target.parent.mkdir(parents=True)
    target.write_text("{not json")
    with pytest.raises(json.JSONDecodeError):
        load_state(tmp_path)


def test_save_state_creates_versions_dir(tmp_path: Path) -> None:
    state = derive_state(_inv(), latest_sha=None, now=FIXED_NOW)
    save_state(state, tmp_path)
    assert (tmp_path / "versions").is_dir()
    assert (tmp_path / STATE_FILE_RELPATH).exists()


def test_write_page_writes_both_files(tmp_path: Path) -> None:
    state = derive_state(_inv(), latest_sha=None, now=FIXED_NOW)
    state_path, html_path = write_page(state, tmp_path, project_title="my paper")
    assert state_path == tmp_path / STATE_FILE_RELPATH
    assert html_path == tmp_path / HTML_FILE_RELPATH
    assert state_path.exists()
    assert html_path.exists()


# ──────────────────────────────────────────── HTML render


def test_render_html_includes_project_title() -> None:
    state = derive_state(_inv(), latest_sha=None, now=FIXED_NOW)
    out = render_html(state, project_title="My Paper")
    assert "<title>Versions — My Paper</title>" in out
    assert "<h1>My Paper: versions</h1>" in out


def test_render_html_escapes_title() -> None:
    state = derive_state(_inv(), latest_sha=None, now=FIXED_NOW)
    out = render_html(state, project_title="<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


def test_render_html_empty_state_shows_friendly_messages() -> None:
    state = derive_state(_inv(), latest_sha=None, now=FIXED_NOW)
    out = render_html(state)
    assert "No deploys yet." in out
    assert "No tagged releases yet." in out
    assert "No untagged snapshots retained." in out
    assert "No open PRs with preview deploys." in out


def test_render_html_lists_latest_sha() -> None:
    snap = Snapshot(sha=SHA_A, size_bytes=100, mtime=1_780_000_000.0)
    state = derive_state(_inv((snap,)), latest_sha=SHA_A, now=FIXED_NOW)
    out = render_html(state)
    assert f"commit {SHA_A[:7]}" in out


def test_render_html_separates_tagged_from_untagged() -> None:
    older = Snapshot(sha=SHA_A, size_bytes=100, mtime=1_700_000_000.0)
    newer = Snapshot(sha=SHA_B, size_bytes=100, mtime=1_780_000_000.0)
    tags = [TagInfo(sha=SHA_A, tag="v1.0.0")]
    state = derive_state(_inv((older, newer)), latest_sha=SHA_B, tag_info=tags, now=FIXED_NOW)
    out = render_html(state)

    tagged_idx = out.index("Tagged releases")
    recent_idx = out.index("Recent commits on main")
    assert tagged_idx < recent_idx
    # v1.0.0 should appear under Tagged releases (before the Recent section)
    v_idx = out.index("v1.0.0")
    assert tagged_idx < v_idx < recent_idx


def test_render_html_pr_link_points_to_pr_subdir() -> None:
    pr_info = PRInfo(number=42, title="Fix abstract", branch="x", sha=SHA_C)
    state = derive_state(
        _inv(pr_dirs={"42": 100}),
        latest_sha=None,
        open_prs=[pr_info],
        now=FIXED_NOW,
    )
    out = render_html(state)
    assert 'href="/pr/42/"' in out
    assert "Fix abstract" in out


def test_render_html_entry_link_points_to_versioned_subdir() -> None:
    snap = Snapshot(sha=SHA_A, size_bytes=100, mtime=1_780_000_000.0)
    state = derive_state(_inv((snap,)), latest_sha=SHA_A, now=FIXED_NOW)
    out = render_html(state)
    assert f'href="/v/{SHA_A}/"' in out


def test_render_html_escapes_pr_title_and_branch() -> None:
    pr_info = PRInfo(
        number=42,
        title="<img src=x onerror=alert(1)>",
        branch="<x>",
        sha=SHA_C,
    )
    state = derive_state(
        _inv(pr_dirs={"42": 100}),
        latest_sha=None,
        open_prs=[pr_info],
        now=FIXED_NOW,
    )
    out = render_html(state)
    assert "<img src=x" not in out
    assert "&lt;img" in out
    assert "&lt;x&gt;" in out


def test_render_html_omits_title_when_unknown() -> None:
    snap = Snapshot(sha=SHA_A, size_bytes=100, mtime=1_780_000_000.0)
    state = derive_state(_inv((snap,)), latest_sha=SHA_A, now=FIXED_NOW)
    out = render_html(state)
    # Title block uses class="title"; should be absent for an untitled entry.
    assert 'class="title"' not in out


def test_render_html_includes_quartobot_attribution() -> None:
    state = derive_state(_inv(), latest_sha=None, now=FIXED_NOW)
    out = render_html(state)
    assert "https://quartobot.github.io/quartobot/" in out
    assert "Generated " in out


# ──────────────────────────────────────────── integration


def test_full_pipeline_inventory_to_disk(tmp_path: Path) -> None:
    """Smoke test: inventory → derive_state → write_page → reload."""
    snapshots = (
        Snapshot(sha=SHA_A, size_bytes=100, mtime=1_700_000_000.0),
        Snapshot(sha=SHA_B, size_bytes=200, mtime=1_780_000_000.0),
    )
    inventory = _inv(snapshots, pr_dirs={"42": 100}, tmp_path=tmp_path)
    tags = [TagInfo(sha=SHA_A, tag="v1.0.0")]
    sha_info = {
        SHA_A: ShaInfo(sha=SHA_A, title="Initial release", date="2025-12-01"),
        SHA_B: ShaInfo(sha=SHA_B, title="Improve abstract", date="2026-04-10"),
    }
    prs = [PRInfo(number=42, title="Tweak figures", branch="fig", sha=SHA_C)]

    state = derive_state(
        inventory,
        latest_sha=SHA_B,
        sha_info=sha_info,
        tag_info=tags,
        open_prs=prs,
        now=FIXED_NOW,
    )
    state_path, html_path = write_page(state, tmp_path, project_title="Paper")

    assert state_path.exists()
    assert html_path.exists()

    reloaded = load_state(tmp_path)
    assert reloaded == state

    html_text = html_path.read_text(encoding="utf-8")
    assert "Paper: versions" in html_text
    assert "v1.0.0" in html_text
    assert "Improve abstract" in html_text
    assert "Tweak figures" in html_text
