# prune-snapshots

Composite action: applies the project's snapshot retention policy to the
`gh-pages` branch.

```yaml
- uses: actions/checkout@v4
  with: { fetch-depth: 0 }   # tags + history; the action needs both
- uses: seandavi/quartobot/actions/prune-snapshots@v0.1
  with:
    project: "."             # where _quarto.yml lives
    mode: "apply"            # "apply" (push prune) or "echo" (read-only)
```

Reads `quartobot.snapshots` from `_quarto.yml` (or bakes in defaults
when absent), inventories the current `gh-pages` tree, decides which
`v/<sha>/` directories to keep, and either echoes the decision or
applies it by replacing pruned directories with redirect stubs and
pushing the result.

## What it does

1. Checks whether the `gh-pages` branch exists. First-run repos skip
   cleanly with a workflow notice.
2. Fetches `gh-pages` into a git worktree under `$RUNNER_TEMP`.
3. Collects tag SHAs from the source repo (tags are the user's "this
   version matters" signal — see retention policy below).
4. Runs `quartobot snapshots inventory` (mode `echo`) or
   `quartobot snapshots apply` (mode `apply`). The CLI's output —
   policy source, inventory, retention decisions, projected size — is
   teed to both the workflow log and the run's Summary tab.
5. If `apply` and the prune produced changes, commits and force-pushes
   the worktree to `gh-pages`. The next deploy step (the render
   workflow's `peaceiris/actions-gh-pages` call) then overlays the new
   `v/<new-sha>/` and updated root files.

## Inputs

| Input | Default | Notes |
|---|---|---|
| `mode` | `apply` | `apply` to push the prune; `echo` for read-only inventory. PR builds should use `echo`. |
| `project` | `.` | Directory containing `_quarto.yml`. |
| `gh-pages-branch` | `gh-pages` | Branch name. |
| `latest-sha` | `${{ github.event.pull_request.head.sha \|\| github.sha }}` | SHA to treat as "latest"; preserved by `retention.latest: keep`. |

## Outputs

| Output | Notes |
|---|---|
| `pruned-count` | Number of `v/<sha>/` directories pruned (always `0` in `echo` mode). |
| `over-budget` | `true` if projected post-prune size still exceeds the budget; `false` otherwise. When `on_over_budget: fail`, the action fails before this can be read. |

## Retention policy

Defaults applied when `_quarto.yml` has no `quartobot.snapshots` block:

```yaml
quartobot:
  snapshots:
    latest: keep              # / always retained
    tagged: keep              # any v/<sha> whose commit has a git tag survives
    recent: 10                # rolling window: last N untagged builds
    pruned_behavior: redirect # write ~1 KB meta-refresh stub at v/<sha>/index.html
    size_budget_mb: 800       # 80% of GitHub Pages 1 GB soft limit
    on_over_budget: fail      # fail the build before drift becomes an email
```

See `docs/retention.md` for the full retention contract and the rationale
for each default.

## Composability

This action is designed to run **before** the render workflow's deploy
step. The deploy step uses `peaceiris/actions-gh-pages@v4` with
`keep_files: true`, which merges the new render output into whatever
state of `gh-pages` exists at deploy time. Pruning first, deploying
second means each render leaves `gh-pages` curated and under budget —
no two-step deploys required from consumers.

## See also

- `template/.github/workflows/pr-closed.yml` — the matching cleanup for
  per-PR previews. Together these two workflows are what keeps
  `gh-pages` bounded over a project's lifetime.
