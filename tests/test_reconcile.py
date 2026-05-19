"""Tests for quartobot.reconcile."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from quartobot.reconcile import (
    accept_bibtex,
    accept_json,
    find_collisions,
    format_collision_for_picker,
    format_outcome,
    manual_picker,
    parse_bib,
    parse_json,
)

FIXED_NOW = datetime(2026, 5, 19, 8, 53, 0, tzinfo=timezone.utc)
BACKUP_SUFFIX = "bak-20260519T085300Z"

SIMPLE_BIB = """\
@article{doi:10.1038/abc,
  author = {Smith and Jones},
  title  = {Foo and bar},
  year   = {2023}
}

@misc{custom_key,
  author = {Doe},
  title  = {A preprint},
  year   = {2024}
}
"""

SIMPLE_JSON = [
    {
        "id": "doi:10.1038/abc",
        "type": "article-journal",
        "title": "Foo and bar (resolved)",
        "issued": {"date-parts": [[2024]]},
    },
    {
        "id": "doi:10.1371/xyz",
        "type": "article-journal",
        "title": "Another paper",
    },
]


# ──────────────────────────────────────────── parse_bib


def test_parse_bib_simple() -> None:
    entries = parse_bib(SIMPLE_BIB)
    assert [e.key for e in entries] == ["doi:10.1038/abc", "custom_key"]
    assert entries[0].entry_type == "article"
    assert entries[1].entry_type == "misc"


def test_parse_bib_preserves_byte_offsets() -> None:
    entries = parse_bib(SIMPLE_BIB)
    for entry in entries:
        assert SIMPLE_BIB[entry.start : entry.end] == entry.text


def test_parse_bib_skips_string_preamble_comment() -> None:
    text = """\
@string{nature = "Nature"}
@preamble{"\\\\newcommand{\\\\foo}{bar}"}
@comment{this is a comment}
@article{realkey,
  title = {Real entry}
}
"""
    entries = parse_bib(text)
    assert [e.key for e in entries] == ["realkey"]


def test_parse_bib_handles_nested_braces_in_fields() -> None:
    text = """\
@article{nested,
  title = {A title with {nested {braces}} inside},
  author = {Smith}
}
"""
    entries = parse_bib(text)
    assert len(entries) == 1
    assert entries[0].key == "nested"
    # Make sure the closing brace search found the OUTER one.
    assert entries[0].text.endswith("}")
    assert "nested {braces}" in entries[0].text


def test_parse_bib_handles_backslash_escapes() -> None:
    text = r"""@article{escaped,
  title = {Title with \{escaped\} braces}
}
"""
    entries = parse_bib(text)
    assert len(entries) == 1
    assert entries[0].key == "escaped"


def test_parse_bib_empty_input() -> None:
    assert parse_bib("") == []


def test_parse_bib_no_entries() -> None:
    text = "% this is a comment file with no entries\n\n# nothing here\n"
    assert parse_bib(text) == []


# ──────────────────────────────────────────── parse_json


def test_parse_json_simple() -> None:
    items = parse_json(json.dumps(SIMPLE_JSON))
    assert len(items) == 2
    assert items[0]["id"] == "doi:10.1038/abc"


def test_parse_json_rejects_non_list() -> None:
    with pytest.raises(ValueError, match="JSON array"):
        parse_json('{"id": "foo"}')


# ──────────────────────────────────────────── find_collisions


def test_find_collisions_one_match() -> None:
    bib = parse_bib(SIMPLE_BIB)
    cols = find_collisions(bib, SIMPLE_JSON)
    assert [c.key for c in cols] == ["doi:10.1038/abc"]
    assert cols[0].bib_entry.key == "doi:10.1038/abc"
    assert cols[0].json_entry["id"] == "doi:10.1038/abc"


def test_find_collisions_no_match() -> None:
    bib = parse_bib(SIMPLE_BIB)
    items = [{"id": "doi:10.1371/different", "title": "x"}]
    assert find_collisions(bib, items) == []


def test_find_collisions_ignores_json_items_without_id() -> None:
    bib = parse_bib(SIMPLE_BIB)
    items = [
        {"id": "doi:10.1038/abc", "title": "x"},
        {"title": "no id"},  # malformed; should be ignored not crash
    ]
    cols = find_collisions(bib, items)
    assert [c.key for c in cols] == ["doi:10.1038/abc"]


def test_find_collisions_orders_by_bib() -> None:
    bib_text = """\
@article{key_b, title = {B}}

@article{key_a, title = {A}}
"""
    bib = parse_bib(bib_text)
    items = [{"id": "key_a"}, {"id": "key_b"}]
    cols = find_collisions(bib, items)
    # Bib order, not JSON order.
    assert [c.key for c in cols] == ["key_b", "key_a"]


# ──────────────────────────────────────────── accept_bibtex


def _setup_project(tmp_path: Path) -> tuple[Path, Path]:
    bib = tmp_path / "references.bib"
    js = tmp_path / "references.json"
    bib.write_text(SIMPLE_BIB, encoding="utf-8")
    js.write_text(json.dumps(SIMPLE_JSON, indent=2) + "\n", encoding="utf-8")
    return bib, js


def test_accept_bibtex_drops_from_json_writes_backup(tmp_path: Path) -> None:
    bib_path, json_path = _setup_project(tmp_path)
    collisions = find_collisions(parse_bib(SIMPLE_BIB), SIMPLE_JSON)
    outcome = accept_bibtex(bib_path, json_path, collisions, now=FIXED_NOW)

    assert outcome.mode == "accept-bibtex"
    assert outcome.decisions == {"doi:10.1038/abc": "bib"}
    assert outcome.bib_change is None
    assert outcome.json_change is not None
    assert outcome.json_change.entries_removed == 1
    assert outcome.json_change.backup_path == tmp_path / f"references.json.{BACKUP_SUFFIX}"

    # The colliding entry is gone from references.json.
    new_items = parse_json(json_path.read_text())
    assert [i["id"] for i in new_items] == ["doi:10.1371/xyz"]

    # references.bib is untouched.
    assert bib_path.read_text() == SIMPLE_BIB

    # Backup contains the pre-mutation content.
    backup = outcome.json_change.backup_path
    assert backup is not None
    backup_items = parse_json(backup.read_text())
    assert [i["id"] for i in backup_items] == ["doi:10.1038/abc", "doi:10.1371/xyz"]


def test_accept_bibtex_dry_run_writes_nothing(tmp_path: Path) -> None:
    bib_path, json_path = _setup_project(tmp_path)
    collisions = find_collisions(parse_bib(SIMPLE_BIB), SIMPLE_JSON)
    outcome = accept_bibtex(
        bib_path, json_path, collisions, dry_run=True, now=FIXED_NOW
    )

    assert outcome.dry_run is True
    assert outcome.json_change is not None
    assert outcome.json_change.entries_removed == 1
    # File contents unchanged.
    items = parse_json(json_path.read_text())
    assert [i["id"] for i in items] == ["doi:10.1038/abc", "doi:10.1371/xyz"]
    # No backup written.
    assert not (tmp_path / f"references.json.{BACKUP_SUFFIX}").exists()


def test_accept_bibtex_no_collisions_no_op(tmp_path: Path) -> None:
    bib_path = tmp_path / "references.bib"
    json_path = tmp_path / "references.json"
    bib_path.write_text("@article{only_bib, title = {x}}\n")
    json_path.write_text(json.dumps([{"id": "only_json"}], indent=2))
    outcome = accept_bibtex(bib_path, json_path, [], now=FIXED_NOW)
    assert outcome.json_change is not None
    assert outcome.json_change.entries_removed == 0
    assert outcome.json_change.backup_path is None


# ──────────────────────────────────────────── accept_json


def test_accept_json_drops_from_bib_writes_backup(tmp_path: Path) -> None:
    bib_path, json_path = _setup_project(tmp_path)
    collisions = find_collisions(parse_bib(SIMPLE_BIB), SIMPLE_JSON)
    outcome = accept_json(bib_path, json_path, collisions, now=FIXED_NOW)

    assert outcome.mode == "accept-json"
    assert outcome.decisions == {"doi:10.1038/abc": "json"}
    assert outcome.json_change is None
    assert outcome.bib_change is not None
    assert outcome.bib_change.entries_removed == 1
    assert outcome.bib_change.backup_path == tmp_path / f"references.bib.{BACKUP_SUFFIX}"

    # The colliding entry is gone from references.bib.
    new_bib = parse_bib(bib_path.read_text())
    assert [e.key for e in new_bib] == ["custom_key"]

    # references.json is untouched.
    items = parse_json(json_path.read_text())
    assert [i["id"] for i in items] == ["doi:10.1038/abc", "doi:10.1371/xyz"]

    # Backup contains the pre-mutation .bib.
    backup = outcome.bib_change.backup_path
    assert backup is not None
    assert backup.read_text() == SIMPLE_BIB


def test_accept_json_dry_run_writes_nothing(tmp_path: Path) -> None:
    bib_path, json_path = _setup_project(tmp_path)
    collisions = find_collisions(parse_bib(SIMPLE_BIB), SIMPLE_JSON)
    outcome = accept_json(
        bib_path, json_path, collisions, dry_run=True, now=FIXED_NOW
    )
    assert outcome.dry_run is True
    assert bib_path.read_text() == SIMPLE_BIB
    assert not (tmp_path / f"references.bib.{BACKUP_SUFFIX}").exists()


# ──────────────────────────────────────────── manual_picker


def test_manual_picker_per_collision_decisions(tmp_path: Path) -> None:
    # Two collisions; pick one each way.
    bib_text = """\
@article{doi:10.1038/abc,
  title = {Bib version of abc}
}

@article{doi:10.1371/xyz,
  title = {Bib version of xyz}
}
"""
    bib_path = tmp_path / "references.bib"
    json_path = tmp_path / "references.json"
    bib_path.write_text(bib_text)
    items = [
        {"id": "doi:10.1038/abc", "title": "JSON version of abc"},
        {"id": "doi:10.1371/xyz", "title": "JSON version of xyz"},
    ]
    json_path.write_text(json.dumps(items, indent=2) + "\n")

    collisions = find_collisions(parse_bib(bib_text), items)
    responses = iter(["b", "j"])  # keep .bib for first, keep .json for second
    outcome = manual_picker(
        bib_path,
        json_path,
        collisions,
        prompt=lambda _c: next(responses),
        now=FIXED_NOW,
    )

    assert outcome.decisions == {
        "doi:10.1038/abc": "bib",
        "doi:10.1371/xyz": "json",
    }
    # bib lost its second entry (the one user said "json wins" on).
    assert [e.key for e in parse_bib(bib_path.read_text())] == ["doi:10.1038/abc"]
    # json lost its first entry (the one user said "bib wins" on).
    assert [i["id"] for i in parse_json(json_path.read_text())] == ["doi:10.1371/xyz"]


def test_manual_picker_skip_leaves_both(tmp_path: Path) -> None:
    bib_path, json_path = _setup_project(tmp_path)
    collisions = find_collisions(parse_bib(SIMPLE_BIB), SIMPLE_JSON)
    outcome = manual_picker(
        bib_path,
        json_path,
        collisions,
        prompt=lambda _c: "s",
        now=FIXED_NOW,
    )
    assert outcome.decisions == {"doi:10.1038/abc": "skip"}
    assert outcome.bib_change is None
    assert outcome.json_change is None
    assert bib_path.read_text() == SIMPLE_BIB


def test_manual_picker_quit_stops_walk(tmp_path: Path) -> None:
    bib_text = """\
@article{key1, title = {1}}

@article{key2, title = {2}}
"""
    bib_path = tmp_path / "references.bib"
    json_path = tmp_path / "references.json"
    bib_path.write_text(bib_text)
    items = [{"id": "key1"}, {"id": "key2"}]
    json_path.write_text(json.dumps(items, indent=2))
    collisions = find_collisions(parse_bib(bib_text), items)
    # Pick "json" for the first (drop key1 from bib), then quit.
    responses = iter(["j", "q"])
    outcome = manual_picker(
        bib_path,
        json_path,
        collisions,
        prompt=lambda _c: next(responses),
        now=FIXED_NOW,
    )
    # Only the first decision was recorded.
    assert outcome.decisions == {"key1": "json"}
    assert outcome.bib_change is not None
    assert outcome.bib_change.entries_removed == 1
    # key2 still in both files.
    assert "key2" in bib_path.read_text()
    items_after = parse_json(json_path.read_text())
    assert {i["id"] for i in items_after} == {"key1", "key2"}


def test_manual_picker_rejects_unknown_response(tmp_path: Path) -> None:
    bib_path, json_path = _setup_project(tmp_path)
    collisions = find_collisions(parse_bib(SIMPLE_BIB), SIMPLE_JSON)
    with pytest.raises(ValueError, match="manual picker"):
        manual_picker(
            bib_path,
            json_path,
            collisions,
            prompt=lambda _c: "x",
            now=FIXED_NOW,
        )


def test_manual_picker_dry_run_writes_nothing(tmp_path: Path) -> None:
    bib_path, json_path = _setup_project(tmp_path)
    collisions = find_collisions(parse_bib(SIMPLE_BIB), SIMPLE_JSON)
    outcome = manual_picker(
        bib_path,
        json_path,
        collisions,
        prompt=lambda _c: "j",
        dry_run=True,
        now=FIXED_NOW,
    )
    assert outcome.dry_run is True
    assert outcome.bib_change is not None
    assert outcome.bib_change.entries_removed == 1
    # Files unchanged on disk.
    assert bib_path.read_text() == SIMPLE_BIB


# ──────────────────────────────────────────── _drop_bib_entries integration


def test_drop_bib_entries_collapses_blank_lines(tmp_path: Path) -> None:
    bib_path, json_path = _setup_project(tmp_path)
    collisions = find_collisions(parse_bib(SIMPLE_BIB), SIMPLE_JSON)
    accept_json(bib_path, json_path, collisions, now=FIXED_NOW)
    new_text = bib_path.read_text()
    # The two-blank-line gap left by removing the first entry should
    # collapse, not leave three consecutive newlines.
    assert "\n\n\n" not in new_text


# ──────────────────────────────────────────── format_outcome


def test_format_outcome_names_each_touched_file(tmp_path: Path) -> None:
    bib_path, json_path = _setup_project(tmp_path)
    collisions = find_collisions(parse_bib(SIMPLE_BIB), SIMPLE_JSON)
    outcome = accept_bibtex(bib_path, json_path, collisions, now=FIXED_NOW)
    out = format_outcome(outcome)
    assert "Reconciled 1 collision(s)" in out
    assert "doi:10.1038/abc — accepted .bib version" in out
    assert "references.json" in out
    assert f"backup: references.json.{BACKUP_SUFFIX}" in out
    assert "To restore" in out


def test_format_outcome_dry_run_marks_would(tmp_path: Path) -> None:
    bib_path, json_path = _setup_project(tmp_path)
    collisions = find_collisions(parse_bib(SIMPLE_BIB), SIMPLE_JSON)
    outcome = accept_bibtex(
        bib_path, json_path, collisions, dry_run=True, now=FIXED_NOW
    )
    out = format_outcome(outcome)
    assert "Would reconcile 1" in out
    assert "Would modify" in out
    assert "would be written to" in out
    assert "To restore" not in out  # only shown when not dry-run


def test_format_outcome_no_collisions() -> None:
    from quartobot.reconcile import ReconcileOutcome

    outcome = ReconcileOutcome(mode="accept-bibtex", decisions={})
    out = format_outcome(outcome)
    assert "No files modified." in out


# ──────────────────────────────────────────── picker rendering


def test_format_collision_for_picker_shows_both_sides() -> None:
    bib = parse_bib(SIMPLE_BIB)
    cols = find_collisions(bib, SIMPLE_JSON)
    out = format_collision_for_picker(cols[0])
    assert "references.bib:" in out
    assert "references.json:" in out
    assert "Smith and Jones" in out  # from bib
    assert "Foo and bar (resolved)" in out  # from json
    assert "[b]ib" in out


# ──────────────────────────────────────────── backup naming


def test_backup_suffix_uses_iso_z_format() -> None:
    from quartobot.reconcile import _backup_path  # type: ignore[attr-defined]

    p = Path("/tmp/references.bib")
    backup = _backup_path(p, FIXED_NOW)
    assert backup.name == f"references.bib.{BACKUP_SUFFIX}"
    # Sortability: another time later in the day sorts after.
    later = FIXED_NOW.replace(hour=9)
    backup_later = _backup_path(p, later)
    assert backup.name < backup_later.name
