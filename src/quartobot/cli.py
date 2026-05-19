"""Command-line interface for quartobot."""

from __future__ import annotations

from pathlib import Path

import click

from quartobot import __version__


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="quartobot")
def main() -> None:
    """quartobot: manuscript-as-software, on Quarto.

    Pre-render and out-of-render tooling for Quarto projects that resolve
    citations through manubot from a pre-render hook.
    """


@main.command()
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
    default=".",
)
@click.option(
    "--recursive/--no-recursive",
    default=True,
    show_default=True,
    help=(
        "When PATH is a directory, descend into subdirectories. "
        "`--no-recursive` only scans files directly under PATH."
    ),
)
def scan(path: Path, recursive: bool) -> None:
    """Scan a Quarto project for cite keys and group by prefix.

    Walks supported files (.qmd, .md, .Rmd, .ipynb) under PATH,
    extracts cite keys (both persistent-identifier ones like @doi: and
    @pmid:, and hand-curated keys), and reports counts and duplicates.
    Pure read; no network. Markdown cells inside .ipynb notebooks are
    scanned; cell index appears alongside line number in duplicate
    reports (e.g. `paper.ipynb:cell3:5`).

    Render outputs and tool caches (`_site/`, `_book/`, `_freeze/`,
    `.quarto/`, `.git/`, `.ipynb_checkpoints/`, `node_modules/`, etc.)
    are skipped at any depth.

    Pure reporter: always exits 0 once it finishes scanning. Repeated
    keys (same-file or cross-file) show up in the listing with `(Nx)`
    counts and a "Duplicates:" section, but they don't gate the exit
    code. `quartobot validate` is the gating step.
    """
    from quartobot.scan import format_scan_result, scan_path

    result = scan_path(path, recursive=recursive)
    relative_to = path if path.is_dir() else path.parent
    click.echo(format_scan_result(result, relative_to=relative_to))


@main.command()
@click.argument("keys", nargs=-1)
@click.option(
    "--from-scan",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
    default=None,
    help="Resolve every persistent-identifier key found by scanning this path.",
)
@click.option(
    "--recursive/--no-recursive",
    default=True,
    show_default=True,
    help=(
        "When --from-scan is a directory, descend into subdirectories. "
        "`--no-recursive` only scans files directly under that path."
    ),
)
@click.option(
    "--output",
    # Plain `str` so `-` (stdout sentinel) passes validation; we coerce
    # to Path in the body when it's a real filesystem target.
    type=str,
    default="references.json",
    show_default=True,
    help=(
        "Path to write the resolved CSL JSON bibliography to. Pass `-` "
        "to stream JSON to stdout instead (no cache write happens in "
        "stdout mode; the summary line goes to stderr)."
    ),
)
@click.option(
    "--cache",
    type=click.Path(file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help=(
        "Optional path to read cached entries from. Cache hits skip the "
        "network call. Defaults to the value of --output for file output, "
        "so resolve is idempotent against its own previous output. In "
        "stdout mode (`--output -`), cache reads only happen when this "
        "flag is set explicitly."
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report what would be resolved without making network calls.",
)
@click.option(
    "--id-mode",
    type=click.Choice(["short-hash", "citation-key"]),
    default="short-hash",
    show_default=True,
    help=(
        "How to populate the CSL `id` field. `citation-key` (the form "
        "expected by the `quartobot` pre-render hook) writes the user's "
        "original `prefix:identifier` so pandoc-citeproc matches prose "
        "keys directly. `short-hash` keeps manubot's hash form for "
        "callers that consume `manubot.cite` output directly."
    ),
)
def resolve(
    keys: tuple[str, ...],
    from_scan: Path | None,
    output: str,
    cache: Path | None,
    dry_run: bool,
    id_mode: str,
    recursive: bool,
) -> None:
    """Pre-fetch citations and write CSL JSON to disk.

    Resolves persistent-identifier cite keys via manubot.cite and writes
    the resulting CSL JSON to --output (default `references.json`), or
    to stdout when --output is `-`. The point isn't to replace what
    manubot does at render — it's to do the network work on a
    developer's machine ahead of push, so CI never sees a Crossref or
    PubMed hiccup. Stdout mode is for one-shot lookups — agents and
    scripts that want to pipe the JSON straight into `jq`.

    Pass keys as arguments (`@doi:10.x/y pmid:12345`) or use --from-scan
    to resolve every persistent-identifier cite found in a project.
    Hand-curated keys (no recognized prefix) are skipped — those live
    in references.bib and pandoc citeproc handles them.

    Exits 1 if any keys fail to resolve, 0 otherwise.
    """
    from quartobot.resolve import (
        STDOUT_SENTINEL,
        collect_resolvable_keys,
        format_outcome,
        resolve_keys,
    )
    from quartobot.scan import strip_pandoc_trailing

    collected: list[str] = []
    for k in keys:
        # Allow either `@doi:10.x/y` or `doi:10.x/y` — strip leading @.
        # Apply the same pandoc-trailing normalization the scan path
        # does, so explicit `@url:…/` keys agree with what citeproc
        # looks up.
        collected.append(strip_pandoc_trailing(k.lstrip("@")))

    if from_scan is not None:
        collected.extend(collect_resolvable_keys(from_scan, recursive=recursive))

    # De-dup while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for k in collected:
        if k not in seen:
            seen.add(k)
            unique.append(k)

    stdout_mode = output == STDOUT_SENTINEL
    output_target: Path | str = output if stdout_mode else Path(output)

    if not unique:
        # Friendly message goes to stderr in stdout mode so the caller's
        # pipe stays empty (a downstream `jq` should see no input, not
        # a stray English sentence).
        click.echo("No persistent-identifier cite keys to resolve.", err=stdout_mode)
        return

    # Cache resolution:
    #   - explicit --cache always honored.
    #   - file output: default cache to output (existing behavior).
    #   - stdout mode without explicit --cache: skip the cache entirely.
    if cache is not None:
        cache_path: Path | None = cache
    elif stdout_mode:
        cache_path = None
    else:
        cache_path = Path(output)

    outcome = resolve_keys(
        unique,
        cache_path=cache_path,
        output_path=output_target,
        dry_run=dry_run,
        id_mode=id_mode,
    )
    # In stdout mode the human-readable summary goes to stderr so stdout
    # stays valid JSON for the next pipe stage.
    click.echo(format_outcome(outcome), err=stdout_mode)
    if outcome.failures:
        raise SystemExit(1)


@main.command()
@click.argument(
    "project",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
def validate(project: Path) -> None:
    """Pre-flight check a Quarto project for the quartobot pattern.

    Runs a battery of static config checks: `_quarto.yml` exists and
    declares `bibliography:`, `project.pre-render` calls
    `quartobot resolve --id-mode citation-key`, `references.json`
    is in the bibliography list, no duplicate cite keys across files.

    Citation-resolution checks (does Crossref actually return metadata
    for this DOI?) are out of scope here — they need network. Run
    `quartobot resolve --dry-run --from-scan .` if you want that.

    Exits 1 if any check fails, 0 if all pass.
    """
    from quartobot.validate import format_outcome, validate_project

    outcome = validate_project(project)
    click.echo(format_outcome(outcome))
    if not outcome.passed:
        raise SystemExit(1)


@main.command("mcp")
def mcp_serve() -> None:
    """Start an MCP server exposing read-only citation tools over stdio.

    Connect an MCP-capable client (Claude Desktop, Codex, Gemini Code
    Assist, Cursor) and the agent can call `resolve_citation`,
    `scan_project`, and `validate_project` as part of a drafting
    workflow — same manubot resolver the CLI's `resolve` uses, no
    parallel implementation.

    Requires the `mcp` extra:

        uv tool install 'quartobot[mcp]'

    See https://quartobot.github.io/quartobot/mcp/ for client setup.
    """
    try:
        from quartobot.mcp import run as run_mcp_server
    except ImportError as e:
        raise click.ClickException(
            "MCP support requires the 'mcp' extra. Install with: uv tool install 'quartobot[mcp]'"
        ) from e
    run_mcp_server()


@main.group()
def snapshots() -> None:
    """Inspect and apply the gh-pages snapshot retention policy.

    The retention policy controls which ``v/<sha>/`` directories on
    gh-pages are kept, which are replaced with redirect stubs, and how
    far gh-pages is allowed to grow before the workflow refuses to push.

    Defaults apply when no ``quartobot.snapshots`` block is present in
    ``_quarto.yml``. Pass ``--help`` to either subcommand for details.
    """


def _resolve_git_facts(
    project: Path,
    latest_sha: str | None,
    tag_shas: str | None,
) -> tuple[str, set[str]]:
    """Fill in ``latest_sha`` and ``tag_shas`` from git when omitted.

    The snapshots module is intentionally git-free; this helper bridges
    it to the local repo so ``quartobot snapshots ...`` is ergonomic
    for ad-hoc local runs without an explicit ``--latest-sha``.

    Args:
        project: Project directory, used as the git working dir.
        latest_sha: User-supplied SHA, or ``None`` to resolve from
            ``git rev-parse HEAD``.
        tag_shas: User-supplied comma-separated SHA list, or ``None``
            to resolve from ``git for-each-ref refs/tags/``.

    Returns:
        ``(resolved_latest_sha, resolved_tag_shas_set)``.

    Raises:
        click.ClickException: If git isn't available or the directory
            isn't a git repository and the caller didn't supply
            ``latest_sha`` explicitly.
    """
    import subprocess

    if latest_sha is None:
        try:
            latest_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=project,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise click.ClickException(
                "could not resolve --latest-sha from git; pass it explicitly"
            ) from exc

    if tag_shas is None:
        try:
            out = subprocess.check_output(
                ["git", "for-each-ref", "--format=%(objectname)", "refs/tags/"],
                cwd=project,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            resolved_tags = {line.strip() for line in out.splitlines() if line.strip()}
        except (FileNotFoundError, subprocess.CalledProcessError):
            resolved_tags = set()
    else:
        resolved_tags = {s.strip() for s in tag_shas.split(",") if s.strip()}

    return latest_sha, resolved_tags


_GH_PAGES_OPT = click.option(
    "--gh-pages-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Path to a checkout of the gh-pages branch.",
)
_PROJECT_OPT = click.option(
    "--project",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=Path("."),
    show_default=True,
    help="Project directory containing _quarto.yml.",
)
_LATEST_SHA_OPT = click.option(
    "--latest-sha",
    type=str,
    default=None,
    help=(
        "Full SHA of the build to treat as 'latest'. Defaults to "
        "`git rev-parse HEAD` in the project directory."
    ),
)
_TAG_SHAS_OPT = click.option(
    "--tag-shas",
    type=str,
    default=None,
    help=(
        "Comma-separated full SHAs of tagged commits. Defaults to all "
        "tag targets in the project's git repo."
    ),
)


@snapshots.command("inventory")
@_GH_PAGES_OPT
@_PROJECT_OPT
@_LATEST_SHA_OPT
@_TAG_SHAS_OPT
def snapshots_inventory(
    gh_pages_dir: Path,
    project: Path,
    latest_sha: str | None,
    tag_shas: str | None,
) -> None:
    """Echo the retention policy and current gh-pages inventory.

    Read-only. Does not modify ``gh-pages-dir``. Use this on PR events
    or for ad-hoc local inspection — it shows what *would* be pruned
    on the next ``apply``.
    """
    from quartobot.snapshots import (
        decide_retention,
        format_log,
        inventory,
        load_policy,
        project_post_prune_bytes,
    )

    load = load_policy(project)
    inv = inventory(gh_pages_dir)
    resolved_latest, resolved_tags = _resolve_git_facts(project, latest_sha, tag_shas)
    decision = decide_retention(
        inv, load.policy, latest_sha=resolved_latest, tagged_shas=resolved_tags
    )
    projected = project_post_prune_bytes(inv, decision, load.policy)
    click.echo(format_log(load, inv, decision, projected))


@snapshots.command("apply")
@_GH_PAGES_OPT
@_PROJECT_OPT
@_LATEST_SHA_OPT
@_TAG_SHAS_OPT
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report what would change without modifying gh-pages-dir.",
)
def snapshots_apply(
    gh_pages_dir: Path,
    project: Path,
    latest_sha: str | None,
    tag_shas: str | None,
    dry_run: bool,
) -> None:
    """Apply the retention policy: prune ``v/<sha>/`` and write stubs.

    Mutates ``gh-pages-dir`` in place. The caller is responsible for
    committing and pushing the result.

    Exits 1 if the projected post-prune total still exceeds
    ``size_budget_mb`` and ``on_over_budget`` is ``fail``.
    """
    from quartobot.snapshots import (
        apply_decision,
        decide_retention,
        format_log,
        inventory,
        load_policy,
        project_post_prune_bytes,
    )

    load = load_policy(project)
    inv = inventory(gh_pages_dir)
    resolved_latest, resolved_tags = _resolve_git_facts(project, latest_sha, tag_shas)
    decision = decide_retention(
        inv, load.policy, latest_sha=resolved_latest, tagged_shas=resolved_tags
    )
    projected = project_post_prune_bytes(inv, decision, load.policy)
    click.echo(format_log(load, inv, decision, projected))

    if not dry_run:
        apply_decision(inv, decision, load.policy)
        click.echo("")
        click.echo(f"Applied: {len(decision.prune)} snapshots pruned in {gh_pages_dir}")

    budget_bytes = load.policy.size_budget_mb * 1_000_000
    if projected > budget_bytes:
        message = (
            f"projected post-prune size {projected / 1_000_000:.1f} MB exceeds "
            f"budget {load.policy.size_budget_mb} MB"
        )
        if load.policy.on_over_budget == "fail":
            raise click.ClickException(message)
        click.echo(f"warning: {message}", err=True)


@main.group()
def versions() -> None:
    """Generate the ``/versions/`` page and its ``state.json`` companion.

    The versions page lists tagged releases, recent commits on main, and
    open PR previews — the discoverability surface that replaces the
    deployed-pages version banner. Run from the render workflow after
    snapshots have been applied; outputs land at
    ``<gh-pages-dir>/versions/``.
    """


@versions.command("update")
@_GH_PAGES_OPT
@_PROJECT_OPT
@_LATEST_SHA_OPT
@_TAG_SHAS_OPT
@click.option(
    "--open-prs",
    "open_prs_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help=(
        "JSON file in `gh pr list --json number,title,headRefName,headRefOid` "
        "shape. Each entry's `headRefOid` is the head sha. If omitted, no "
        "PRs are listed (workflows on the main branch can pass an empty "
        "list or skip this flag entirely)."
    ),
)
@click.option(
    "--sha-info",
    "sha_info_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help=(
        "TSV file with three columns: full-sha, commit-subject, ISO-date. "
        "Output of `git log --format='%H%x09%s%x09%aI'`. Used to enrich "
        "the version entries with commit titles and dates; entries with "
        "no matching row fall back to the snapshot's mtime date and a "
        "missing title."
    ),
)
@click.option(
    "--project-title",
    type=str,
    default="manuscript",
    show_default=True,
    help="Title shown in the page's <h1> and <title> tags.",
)
def versions_update(
    gh_pages_dir: Path,
    project: Path,
    latest_sha: str | None,
    tag_shas: str | None,
    open_prs_path: Path | None,
    sha_info_path: Path | None,
    project_title: str,
) -> None:
    """Derive state from gh-pages + git facts and write the versions page.

    Reads the on-disk gh-pages inventory, cross-references with caller-
    supplied git tag and commit metadata, and writes
    ``versions/state.json`` and ``versions/index.html`` under
    ``gh-pages-dir``. Idempotent: running again with the same inputs
    produces a byte-identical result modulo the ``generated_at``
    timestamp.

    The caller (typically the render workflow) is responsible for
    committing and pushing the result.
    """
    import json as _json

    from quartobot.snapshots import inventory as _inventory
    from quartobot.versions import (
        PRInfo,
        ShaInfo,
        TagInfo,
        derive_state,
        write_page,
    )

    resolved_latest, resolved_tag_shas = _resolve_git_facts(project, latest_sha, tag_shas)

    # Tag info — resolved to (sha, tag) pairs. We only know the shas
    # from _resolve_git_facts; ask git for the corresponding tag names.
    tag_info: list[TagInfo] = []
    if resolved_tag_shas:
        import subprocess

        try:
            raw = subprocess.check_output(
                [
                    "git",
                    "for-each-ref",
                    "--format=%(objectname)%09%(refname:short)",
                    "refs/tags/",
                ],
                cwd=project,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            for line in raw.splitlines():
                if "\t" not in line:
                    continue
                sha, tag = line.split("\t", 1)
                if sha in resolved_tag_shas:
                    tag_info.append(TagInfo(sha=sha, tag=tag))
        except (FileNotFoundError, subprocess.CalledProcessError):
            # No git, or no tags. Silent fallback — the inventory still
            # gets a versions page, just with no tagged-release section.
            pass

    # PRs — gh CLI JSON shape.
    open_prs: list[PRInfo] = []
    if open_prs_path is not None:
        raw_prs = _json.loads(open_prs_path.read_text(encoding="utf-8"))
        for p in raw_prs:
            try:
                open_prs.append(
                    PRInfo(
                        number=int(p["number"]),
                        title=str(p["title"]),
                        branch=str(p.get("headRefName", "")),
                        sha=str(p.get("headRefOid", "")),
                        date=p.get("updatedAt"),
                    )
                )
            except (KeyError, ValueError, TypeError) as exc:
                raise click.ClickException(
                    f"malformed PR entry in {open_prs_path}: {p!r} ({exc})"
                ) from exc

    # Commit display metadata — TSV `<sha>\t<subject>\t<iso-date>`.
    sha_info: dict[str, ShaInfo] = {}
    if sha_info_path is not None:
        for line in sha_info_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 1:
                continue
            sha = parts[0].strip()
            if not sha:
                continue
            title = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
            date = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
            sha_info[sha] = ShaInfo(sha=sha, title=title, date=date)

    inv = _inventory(gh_pages_dir)
    state = derive_state(
        inv,
        latest_sha=resolved_latest,
        sha_info=sha_info,
        tag_info=tag_info,
        open_prs=open_prs,
    )
    state_path, html_path = write_page(state, gh_pages_dir, project_title=project_title)

    click.echo(
        f"Wrote {state_path.relative_to(gh_pages_dir)} "
        f"and {html_path.relative_to(gh_pages_dir)}"
    )
    click.echo(
        f"  {len(state.entries)} version entries "
        f"({sum(1 for e in state.entries if e.tag)} tagged), "
        f"{len(state.prs)} open PR previews"
    )


@main.command()
@click.argument(
    "project",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
@click.option(
    "--project-type",
    type=click.Choice(["auto", "manuscript", "book"]),
    default="auto",
    show_default=True,
    help=(
        "Quarto project shape. `auto` detects from an existing _quarto.yml "
        "and falls back to manuscript when there's nothing to detect from."
    ),
)
def init(project: Path, project_type: str) -> None:
    """Scaffold the citation pipeline into an existing Quarto project.

    Writes only what the citation pipeline needs: `_quarto.yml` (when
    absent) wired with the `quartobot resolve` pre-render hook and a
    `bibliography:` list, a seed `references.bib`, and `.gitignore`
    augments so `references.json` stays out of the repo.

    Conservative — never overwrites existing files. If `_quarto.yml`
    already exists, prints a YAML snippet to merge in manually.

    The GitHub Actions render workflow, version banner, and PR-preview
    cleanup live in `quartobot use github-ci`. Run that after `init`
    if you want them.
    """
    from quartobot.init_project import format_outcome, init_project

    outcome = init_project(project, project_type=project_type)
    click.echo(format_outcome(outcome, project=project))


@main.group()
def use() -> None:
    """Wire optional capabilities into a quartobot project.

    Each subcommand is opinionated about one thing and is idempotent
    — re-running is safe; files already on disk are left alone. The
    list will grow over time; today `github-ci` is the first
    inhabitant.
    """


@use.command("github-ci")
@click.argument(
    "project",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
@click.option(
    "--project-type",
    type=click.Choice(["auto", "manuscript", "book"]),
    default="auto",
    show_default=True,
    help=(
        "Quarto project shape. `auto` detects from an existing _quarto.yml "
        "and falls back to manuscript when there's nothing to detect from."
    ),
)
@click.option(
    "--with-versioned-snapshots",
    is_flag=True,
    default=False,
    help=(
        "Opt into the manubot-style pipeline: per-commit `/v/<sha>/` "
        "permalink deploys, snapshot retention policy, and the in-page "
        "version banner. The default (lean) pipeline ships latest at "
        "root, PR previews, and a `/versions/` page; the versioned "
        "pipeline adds the per-commit permalink layer on top."
    ),
)
def use_github_ci(
    project: Path,
    project_type: str,
    with_versioned_snapshots: bool,
) -> None:
    """Scaffold the GitHub Actions render workflow.

    Default (lean) pipeline writes ``.github/workflows/render.yml``
    pointing at the lean reusable workflow, plus the PR-preview
    cleanup workflow. The manuscript ships at ``/``, PR previews
    land at ``/pr/<n>/``, and the generated ``/versions/`` page is
    the version-discovery surface.

    Opt into the v0.1 manubot-style pipeline with
    ``--with-versioned-snapshots``: adds per-commit ``/v/<sha>/``
    permalink deploys, snapshot retention pruning, and the in-page
    version-banner include. The command then also writes the banner
    template files and prints a YAML snippet to merge into
    ``_quarto.yml`` for the banner include.

    Idempotent. Files already present are reported as skipped.
    """
    from quartobot.use_github_ci import apply_github_ci, format_outcome

    outcome = apply_github_ci(
        project,
        project_type=project_type,
        with_versioned_snapshots=with_versioned_snapshots,
    )
    click.echo(format_outcome(outcome, project=project))


if __name__ == "__main__":
    main()
