---
title: Install
description: Every install method for the quartobot CLI, when to use which.
---

A few ways to get `quartobot` on your machine, in roughly descending
order of how often you'll want each.

## Recommended: `uv tool install` from PyPI

:::note
Don't have `uv` yet? See the
[uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).
:::

```bash
uv tool install quartobot
```

For unreleased main, install from git instead:

```bash
uv tool install git+https://github.com/seandavi/quartobot
```

This puts `quartobot` on your user `PATH` (typically `~/.local/bin` or
similar) so commands like `quartobot init`, `scan`, `validate`, and
`resolve` work from any project directory without a venv activation
dance.

[uv](https://docs.astral.sh/uv/) manages the underlying Python and
dependencies in an isolated environment behind the scenes. You don't
need to maintain a virtualenv yourself.

Pin a specific ref:

```bash
uv tool install git+https://github.com/seandavi/quartobot@<branch-or-tag-or-sha>
```

Upgrade later:

```bash
uv tool upgrade quartobot
```

Uninstall:

```bash
uv tool uninstall quartobot
```

## If you have `pipx` instead of `uv`

If `pipx` is already part of your Python workflow and you'd rather not
take on the uv toolchain, `pipx` installs `quartobot` as a CLI on your
user `PATH` the same way:

```bash
pipx install git+https://github.com/seandavi/quartobot
```

The trade-off: `pipx` doesn't manage the underlying Python install, so
Python ≥ 3.10 needs to be on the system already. `quartobot init`,
`scan`, `validate`, and `resolve` then work the same as the `uv tool
install` path.

## One-shot: `uvx`

Run `quartobot` without installing it persistently. Useful for trying
it out, scripted one-off jobs, or pinning a specific version in CI
without polluting the host install.

```bash
uvx --from git+https://github.com/seandavi/quartobot quartobot --help
uvx --from git+https://github.com/seandavi/quartobot quartobot resolve --from-scan .
```

The `--from` flag is required because the package name and the command
name are the same. Without it, `uvx` would look for a PyPI package
literally named `quartobot`.

## `pip install` from PyPI

`quartobot` is on PyPI since v0.2.0, so the registry path works too:

```bash
pip install quartobot
```

The trade-off: `pip install` into a system Python isn't recommended
on modern Linux distros (you'll likely hit
[PEP 668](https://peps.python.org/pep-0668/) "externally-managed-environment"
errors). Use `uv tool install quartobot` instead, or
`pipx install quartobot`, or install into a project venv with
`uv pip install quartobot`.

## For repo development

Clone and install editable:

```bash
git clone https://github.com/seandavi/quartobot.git
cd quartobot
uv pip install -e .
```

For the full dev environment (lint, type-check, test):

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run mypy
```

## Requirements

- **Python ≥ 3.10.** `uv tool install` manages this automatically.
- **Quarto ≥ 1.4** if you're rendering documents. [Install Quarto.](https://quarto.org/docs/get-started/)
- **No system manubot install needed.** `quartobot` declares manubot
  as a dependency; `uv tool install` brings it along.

## Verify Quarto can find it

The `quartobot resolve` pre-render hook in `_quarto.yml` runs as a
subprocess of `quarto render`, which means `quartobot` has to be on
the shell `PATH` Quarto sees — not just on the venv-activated PATH in
your terminal. `uv tool install` puts it there; an editable install
into a project venv does not.

```bash
quartobot --version
quartobot --help
quarto check
which quartobot
```

If `quartobot --version` works in your shell but `quarto render`
fails with "command not found: quartobot", the install directory
(typically `~/.local/bin`) isn't on the shell PATH for the user
Quarto runs as. For `uv tool install`, `uv tool update-shell` adds
it; for `pipx`, `pipx ensurepath` does the same. A login reload then
picks it up.
