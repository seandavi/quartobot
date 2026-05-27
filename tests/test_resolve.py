"""Tests for the resolve command and module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from quartobot.cli import main
from quartobot.resolve import (
    Resolution,
    ResolveOutcome,
    _build_cache_index,
    _load_existing,
    _standard_id_from_note,
    collect_resolvable_keys,
    format_outcome,
    resolve_keys,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample.qmd"


# ----------------------------------------------------------- helpers


class _FakeCiteKey:
    """Stand-in for manubot.cite.citekey.CiteKey for tests."""

    def __init__(self, raw: str, infer_prefix: bool = True) -> None:
        self.input_id = raw
        # Use the raw form as the standard_id — matches manubot for
        # well-formed `prefix:id` inputs.
        self.standard_id = raw


def _fake_csl_item(citekey, **_kwargs):
    """Stand-in for citekey_to_csl_item — return a deterministic stub."""
    sid = citekey.standard_id
    # Predictable short_id: first 4 chars of the identifier portion.
    after = sid.split(":", 1)[-1]
    short = after.replace("/", "").replace(".", "")[:8] or "shortid"
    return {
        "id": f"SHORT_{short}",
        "title": f"Stub for {sid}",
        "type": "article-journal",
        "note": f"standard_id: {sid}",
    }


# ----------------------------------------------------------- collect


def test_collect_only_persistent_ids(tmp_path):
    qmd = tmp_path / "doc.qmd"
    qmd.write_text(
        "Persistent: @doi:10.1/x and @pmid:99.\nHand-curated: @somekey — should be skipped.\n"
    )
    keys = collect_resolvable_keys(tmp_path)
    assert "doi:10.1/x" in keys
    assert "pmid:99" in keys
    assert "somekey" not in keys


def test_collect_dedupes_repeats(tmp_path):
    a = tmp_path / "a.qmd"
    b = tmp_path / "b.qmd"
    a.write_text("@doi:10.1/x\n")
    b.write_text("@doi:10.1/x repeated.\n")
    keys = collect_resolvable_keys(tmp_path)
    assert keys.count("doi:10.1/x") == 1


def test_collect_handles_bare_doi(tmp_path):
    qmd = tmp_path / "doc.qmd"
    qmd.write_text("Bare: @10.1038/abc.\n")
    keys = collect_resolvable_keys(tmp_path)
    # Bare DOI is classified under "doi" prefix.
    assert any(k.startswith("doi:10.1038/") for k in keys)


def test_collect_empty_project(tmp_path):
    assert collect_resolvable_keys(tmp_path) == []


# ----------------------------------------------------------- _load_existing + cache index


def test_load_existing_missing_returns_empty(tmp_path):
    assert _load_existing(tmp_path / "missing.json") == []


def test_load_existing_invalid_json_returns_empty(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json")
    assert _load_existing(p) == []


def test_load_existing_non_list_returns_empty(tmp_path):
    p = tmp_path / "obj.json"
    p.write_text('{"id": "x"}')
    assert _load_existing(p) == []


def test_load_existing_round_trip(tmp_path):
    p = tmp_path / "ok.json"
    items = [{"id": "abc"}, {"id": "def"}]
    p.write_text(json.dumps(items))
    assert _load_existing(p) == items


def test_build_cache_index_extracts_standard_id():
    items = [
        {"id": "abc", "note": "Some context\nstandard_id: doi:10.1/x"},
        {"id": "def", "note": "standard_id: pmid:99"},
    ]
    index = _build_cache_index(items)
    assert "doi:10.1/x" in index
    assert "pmid:99" in index


def test_build_cache_index_skips_entries_without_standard_id():
    items = [{"id": "abc", "note": "just a free-text note"}, {"id": "def"}]
    assert _build_cache_index(items) == {}


# ----------------------------------------------------------- resolve_keys


def test_resolve_dry_run_no_network():
    keys = ["doi:10.1/x", "pmid:99"]
    # Even though we don't pass a mock, dry_run shouldn't touch manubot.
    outcome = resolve_keys(keys, dry_run=True)
    assert len(outcome.successes) == 2
    assert all(r.short_id is None for r in outcome.successes)
    assert outcome.entries_written == 0


def test_resolve_writes_csl_json(tmp_path):
    out = tmp_path / "references.json"
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        outcome = resolve_keys(
            ["doi:10.1/x", "pmid:99"],
            output_path=out,
            cache_path=out,
        )
    assert outcome.entries_written == 2
    data = json.loads(out.read_text())
    ids = sorted(item["id"] for item in data)
    assert ids == sorted(["SHORT_101x", "SHORT_99"])


def test_resolve_cache_hit_skips_resolution(tmp_path):
    # Pre-populate the output file with one entry.
    out = tmp_path / "references.json"
    out.write_text(
        json.dumps(
            [
                {"id": "SHORT_101x", "title": "Cached", "note": "standard_id: doi:10.1/x"},
            ]
        )
    )

    calls: list[str] = []

    def _track(citekey, **_):
        calls.append(citekey.standard_id)
        return _fake_csl_item(citekey)

    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _track),
    ):
        outcome = resolve_keys(
            ["doi:10.1/x", "pmid:99"],
            cache_path=out,
            output_path=out,
        )
    assert outcome.cache_hits == 1
    # Only the uncached key triggered a resolver call.
    assert calls == ["pmid:99"]


def test_resolve_records_failure(tmp_path):
    def _raises(citekey, **_):
        raise RuntimeError("crossref 404")

    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _raises),
    ):
        outcome = resolve_keys(["doi:10.1/missing"])
    assert len(outcome.failures) == 1
    assert outcome.failures[0].error == "crossref 404"


def test_resolve_records_resolver_returning_none(tmp_path):
    def _none(citekey, **_):
        return None

    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _none),
    ):
        outcome = resolve_keys(["doi:10.1/foo"])
    assert len(outcome.failures) == 1
    assert "None" in (outcome.failures[0].error or "")


def test_resolve_output_sorted_for_diff_stability(tmp_path):
    out = tmp_path / "references.json"
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        resolve_keys(
            ["pmid:99", "doi:10.1/x"],  # input in non-alpha order
            output_path=out,
        )
    items = json.loads(out.read_text())
    ids = [item["id"] for item in items]
    assert ids == sorted(ids)


# ----------------------------------------------------------- _standard_id_from_note


def test_standard_id_from_note_extracts_value():
    note = "free-text line\nstandard_id: doi:10.1/x\ntrailing"
    assert _standard_id_from_note(note) == "doi:10.1/x"


def test_standard_id_from_note_none_input():
    assert _standard_id_from_note(None) is None


def test_standard_id_from_note_non_string_input():
    assert _standard_id_from_note(42) is None


def test_standard_id_from_note_missing_marker():
    assert _standard_id_from_note("just a free-text note") is None


def test_standard_id_from_note_first_match_wins():
    note = "standard_id: doi:10.1/first\nstandard_id: pmid:99"
    assert _standard_id_from_note(note) == "doi:10.1/first"


# ----------------------------------------------------------- id_mode


def test_id_mode_short_hash_default_preserves_manubot_id(tmp_path):
    """Default id_mode keeps the resolver's `id` field unchanged."""
    out = tmp_path / "references.json"
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        resolve_keys(["doi:10.1/x"], output_path=out)
    data = json.loads(out.read_text())
    assert data[0]["id"] == "SHORT_101x"


def test_id_mode_citation_key_rewrites_id(tmp_path):
    """`citation-key` rewrites `id` to the user's prose form."""
    out = tmp_path / "references.json"
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        resolve_keys(["doi:10.1/x"], output_path=out, id_mode="citation-key")
    data = json.loads(out.read_text())
    assert data[0]["id"] == "doi:10.1/x"


def test_id_mode_citation_key_prefers_input_over_canonical(tmp_path):
    """When manubot canonicalizes a prefix (pmid → pubmed), `id` matches
    the user's prose form, not the canonical form. The prose is the
    source of truth for what citeproc will look for.
    """

    class _CanonicalizingFake(_FakeCiteKey):
        def __init__(self, raw: str, infer_prefix: bool = True) -> None:
            super().__init__(raw, infer_prefix)
            # Mimic manubot's pmid → pubmed canonicalization.
            if raw.startswith("pmid:"):
                self.standard_id = "pubmed:" + raw.split(":", 1)[1]

    def _csl_using_standard_id(citekey, **_):
        sid = citekey.standard_id
        return {
            "id": f"SHORT_{sid.split(':', 1)[1]}",
            "title": f"Stub for {sid}",
            "type": "article-journal",
            "note": f"standard_id: {sid}",
        }

    out = tmp_path / "references.json"
    with (
        patch("manubot.cite.citekey.CiteKey", _CanonicalizingFake),
        patch("manubot.cite.citekey.citekey_to_csl_item", _csl_using_standard_id),
    ):
        resolve_keys(["pmid:26678082"], output_path=out, id_mode="citation-key")
    data = json.loads(out.read_text())
    # User wrote `pmid:` in prose — `id` must be `pmid:`, not `pubmed:`.
    assert data[0]["id"] == "pmid:26678082"


def test_id_mode_citation_key_orphan_cache_falls_back_to_standard_id(tmp_path):
    """Cache entries with no resolution this run fall back to their
    standard_id (from the `note` field) for the rewritten id, since
    we don't know what the user's prose form was."""
    out = tmp_path / "references.json"
    # Pre-populate cache with an entry not asked about this run.
    out.write_text(
        json.dumps(
            [
                {
                    "id": "SHORT_orphaned",
                    "title": "Orphan from a prior run",
                    "note": "standard_id: doi:10.1/orphan",
                }
            ]
        )
    )
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        resolve_keys(
            ["doi:10.1/x"],
            cache_path=out,
            output_path=out,
            id_mode="citation-key",
        )
    data = json.loads(out.read_text())
    ids = {item["id"] for item in data}
    # The orphan was preserved with its standard_id from `note`.
    assert "doi:10.1/orphan" in ids
    # The resolved key uses the user's prose form.
    assert "doi:10.1/x" in ids


def test_id_mode_citation_key_handles_multiple_keys(tmp_path):
    """Every successful resolution gets the user's prose key as `id`."""
    out = tmp_path / "references.json"
    keys = ["doi:10.1/x", "pmid:99", "arxiv:2104.10729"]
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        resolve_keys(keys, output_path=out, id_mode="citation-key")
    data = json.loads(out.read_text())
    ids = {item["id"] for item in data}
    assert ids == set(keys)


# ----------------------------------------------------------- format_outcome


def test_format_no_keys():
    outcome = ResolveOutcome()
    assert "No persistent-identifier" in format_outcome(outcome)


def test_format_lists_successes_and_failures():
    outcome = ResolveOutcome()
    outcome.resolutions = [
        Resolution(
            key="doi:10.1/x",
            standard_id="doi:10.1/x",
            short_id="ABC",
            succeeded=True,
        ),
        Resolution(
            key="doi:10.1/y",
            standard_id="doi:10.1/y",
            short_id=None,
            succeeded=False,
            error="404",
        ),
    ]
    outcome.entries_written = 1
    outcome.output_path = Path("references.json")
    out = format_outcome(outcome)
    assert "✓" in out
    assert "✗" in out
    assert "1 resolved" in out
    assert "1 failed" in out
    assert "references.json" in out


# ----------------------------------------------------------- CLI


def test_cli_no_keys_no_scan_exits_zero():
    runner = CliRunner()
    result = runner.invoke(main, ["resolve"])
    assert result.exit_code == 0
    assert "No persistent-identifier" in result.output


def test_cli_dry_run_does_not_write(tmp_path):
    qmd = tmp_path / "doc.qmd"
    qmd.write_text("Cite: @doi:10.1/x.\n")
    out = tmp_path / "references.json"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "resolve",
            "--from-scan",
            str(tmp_path),
            "--output",
            str(out),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert not out.exists()


def test_cli_writes_output_file(tmp_path):
    qmd = tmp_path / "doc.qmd"
    qmd.write_text("Cite: @doi:10.1/x.\n")
    out = tmp_path / "references.json"

    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "resolve",
                "--from-scan",
                str(tmp_path),
                "--output",
                str(out),
            ],
        )
    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    assert len(data) == 1


def test_cli_strips_leading_at():
    """`quartobot resolve @doi:10.1/x` should work the same as `doi:10.1/x`."""
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["resolve", "@doi:10.1/x"])
    assert result.exit_code == 0, result.output


def test_cli_exits_one_on_failure(tmp_path):
    def _raises(citekey, **_):
        raise RuntimeError("nope")

    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _raises),
    ):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["resolve", "doi:10.1/missing"])
    assert result.exit_code == 1


def test_cli_id_mode_citation_key(tmp_path):
    """The `--id-mode citation-key` flag is plumbed end-to-end."""
    qmd = tmp_path / "doc.qmd"
    qmd.write_text("Cite: @doi:10.1/x.\n")
    out = tmp_path / "references.json"

    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "resolve",
                "--from-scan",
                str(tmp_path),
                "--output",
                str(out),
                "--id-mode",
                "citation-key",
            ],
        )
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert data[0]["id"] == "doi:10.1/x"


def test_cli_id_mode_rejects_invalid_value():
    """Click should reject an unknown --id-mode value."""
    runner = CliRunner()
    result = runner.invoke(main, ["resolve", "--id-mode", "nonsense"])
    assert result.exit_code != 0
    assert "Invalid value" in result.output or "Invalid choice" in result.output


# ----------------------------------------------------------- --output -


def test_cli_output_dash_streams_json_to_stdout():
    """`resolve --output -` writes valid CSL JSON to stdout and nothing else."""
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        runner = CliRunner()
        result = runner.invoke(main, ["resolve", "--output", "-", "doi:10.1/x"])
    assert result.exit_code == 0, (result.stdout, result.stderr)
    # stdout is the JSON payload — must parse and contain our fixture.
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert any(item.get("title") == "Stub for doi:10.1/x" for item in data)
    # The human-readable summary is on stderr, not stdout.
    assert "resolved" in result.stderr
    assert "resolved" not in result.stdout


def test_cli_output_dash_no_cache_write(tmp_path):
    """Stdout mode without --cache writes nothing to disk."""
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as iso:
            result = runner.invoke(main, ["resolve", "--output", "-", "doi:10.1/x"])
            # The CLI runs with the isolated fs as cwd; that's where any
            # accidental default-cache write would land.
            iso_dir = Path(iso)
            stray = list(iso_dir.iterdir())
    assert result.exit_code == 0, (result.stdout, result.stderr)
    assert not (iso_dir / "references.json").exists()
    assert stray == [], f"stdout mode left files behind: {stray}"


def test_cli_output_dash_honors_explicit_cache(tmp_path):
    """`--output -` with explicit `--cache <path>` still reads the cache."""
    cache = tmp_path / "cached.json"
    cache.write_text(
        json.dumps(
            [
                {
                    "id": "SHORT_101x",
                    "title": "Cached title",
                    "type": "article-journal",
                    "note": "standard_id: doi:10.1/x",
                }
            ]
        )
    )
    calls: list[str] = []

    def _track(citekey, **_):
        calls.append(citekey.standard_id)
        return _fake_csl_item(citekey)

    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _track),
    ):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["resolve", "--output", "-", "--cache", str(cache), "doi:10.1/x"],
        )
    assert result.exit_code == 0, (result.stdout, result.stderr)
    # Cache hit — manubot's resolver was never invoked.
    assert calls == []
    data = json.loads(result.stdout)
    assert any(item.get("title") == "Cached title" for item in data)


def test_cli_output_dash_no_keys_message_on_stderr():
    """Empty resolve in stdout mode keeps stdout empty for clean pipes."""
    runner = CliRunner()
    result = runner.invoke(main, ["resolve", "--output", "-"])
    assert result.exit_code == 0
    assert result.stdout == ""
    assert "No persistent-identifier" in result.stderr


def test_resolve_keys_stdout_mode_writes_to_sys_stdout(capsys):
    """Library-level: `output_path="-"` writes JSON to sys.stdout."""
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        outcome = resolve_keys(["doi:10.1/x"], output_path="-")
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert outcome.wrote_stdout is True
    assert outcome.output_path is None
    assert outcome.entries_written == 1
    assert data[0]["title"] == "Stub for doi:10.1/x"


# --------------------------------------------------- BibLaTeX side-output


def test_resolve_writes_bib_output_alongside_csl_json(tmp_path):
    """When bib_output_path is set, write the BibLaTeX artifact too."""
    out = tmp_path / "references.json"
    bib = tmp_path / "references.resolved.bib"
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
        patch(
            "quartobot.resolve._csljson_to_biblatex",
            lambda txt: "@misc{stub, title={Stub}}\n",
        ),
    ):
        outcome = resolve_keys(
            ["doi:10.1/x"],
            output_path=out,
            cache_path=out,
            bib_output_path=bib,
        )
    assert outcome.bib_output_path == bib
    assert bib.read_text() == "@misc{stub, title={Stub}}\n"
    assert out.exists(), "CSL JSON cache should also be written"


def test_resolve_skips_bib_in_stdout_mode(tmp_path, capsys):
    """Stdout mode is the one-shot piping path — no .bib file written."""
    bib = tmp_path / "references.resolved.bib"
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
        patch(
            "quartobot.resolve._csljson_to_biblatex",
            lambda txt: "should not be called\n",
        ),
    ):
        outcome = resolve_keys(
            ["doi:10.1/x"],
            output_path="-",
            bib_output_path=bib,
        )
    capsys.readouterr()
    assert outcome.bib_output_path is None
    assert not bib.exists()


def test_resolve_skips_bib_when_no_entries(tmp_path):
    """Pandoc rejects an empty CSL JSON array — don't call it for nothing."""
    bib = tmp_path / "references.resolved.bib"
    out = tmp_path / "references.json"
    # Resolution fails for an unrecognized key; merged stays empty.
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", lambda *a, **k: None),
    ):
        outcome = resolve_keys(
            ["doi:10.1/x"],
            output_path=out,
            cache_path=out,
            bib_output_path=bib,
        )
    assert outcome.bib_output_path is None
    assert not bib.exists()


def test_csljson_to_biblatex_raises_when_pandoc_and_quarto_missing():
    """A clear error is more useful than a generic FileNotFoundError.

    Both ``pandoc`` and ``quarto`` have to be missing to trip this —
    the helper falls back to ``quarto pandoc`` when system pandoc
    isn't on PATH (CI runners with Quarto installed but bundled
    pandoc unexposed).
    """
    from quartobot.resolve import _csljson_to_biblatex

    with patch("quartobot.resolve.shutil.which", return_value=None):
        try:
            _csljson_to_biblatex("[]")
        except RuntimeError as exc:
            assert "neither `pandoc` nor `quarto`" in str(exc)
        else:
            raise AssertionError("expected RuntimeError when both missing")


def test_csljson_to_biblatex_falls_back_to_quarto_pandoc(tmp_path):
    """When `pandoc` is missing but `quarto` is on PATH, use it."""
    import subprocess as real_subprocess

    from quartobot.resolve import _csljson_to_biblatex

    def fake_which(name: str) -> str | None:
        return "/usr/local/bin/quarto" if name == "quarto" else None

    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return real_subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="@misc{x}\n", stderr=""
        )

    with (
        patch("quartobot.resolve.shutil.which", fake_which),
        patch("quartobot.resolve.subprocess.run", fake_run),
    ):
        out = _csljson_to_biblatex("[]")

    assert out == "@misc{x}\n"
    assert captured["cmd"][:2] == ["/usr/local/bin/quarto", "pandoc"]


def test_cli_resolve_default_writes_bib(tmp_path):
    """CLI default: pre-render hook produces .resolved.bib without --bib-output."""
    fixture = (
        '[\n  {"id": "doi:10.1/x", "title": "Cite me",\n'
        '   "type": "article-journal",\n'
        '   "note": "standard_id: doi:10.1/x"}\n]\n'
    )
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as iso_dir:
        (Path(iso_dir) / "doc.qmd").write_text("Cite @doi:10.1/x.\n")
        # Pre-populate cache so the run hits the cache path (no manubot calls).
        (Path(iso_dir) / "references.json").write_text(fixture)
        with patch(
            "quartobot.resolve._csljson_to_biblatex",
            lambda txt: "@article{doi:10.1/x, title={Cite me}}\n",
        ):
            result = runner.invoke(
                main,
                ["resolve", "--from-scan", ".", "--id-mode", "citation-key"],
            )
        assert result.exit_code == 0, result.output
        bib = Path(iso_dir) / "references.resolved.bib"
        assert bib.exists()
        assert "doi:10.1/x" in bib.read_text()
