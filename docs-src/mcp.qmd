---
title: MCP server
description: Citation grounding for agentic authoring tools — Claude Desktop, Codex, Gemini, Cursor.
---

LLM-driven drafting workflows are the new pressure point for citation
handling. The model proposes a passage, the author asks "where's that
from?", and someone — model or human — fills in a reference. Today the
model hallucinates the DOI, links to whatever URL appears in its
training data, or breaks the loop and dumps the work in the author's
lap.

Manubot solves exactly this problem (resolve `doi:`, `pmid:`,
`arxiv:`, `isbn:`, `url:`, `wikidata:`, `pmc:` keys to canonical
metadata via the source APIs) and has been doing it for eight years
— but only inside its own pandoc filter. An agent calling out from
Claude Desktop, Codex, or Gemini Code Assist can't reach it.

`quartobot mcp` closes that gap. It starts a stdio MCP server that
hands the agent three read-only tools backed by the same code the CLI
uses for the pre-render hook. Eight years of accumulated source-API
bug fixes show up as one primitive in the agent's toolkit; nobody has
to reimplement them.

## Install

The server ships as an opt-in extra. Base `quartobot` installs don't
pull the MCP SDK.

```bash
uv tool install 'quartobot[mcp]'
```

If `quartobot` is already installed without the extra, re-running with
`[mcp]` upgrades in place. Confirm:

```bash
quartobot mcp --help
```

## Tools

The server registers three tools. All are read-only — nothing writes
to your filesystem.

### `resolve_citation(cite_key)`

Resolve a single persistent-identifier key to CSL JSON. Direct wrap of
`manubot.cite.citekey_to_csl_item` — same resolver `quartobot resolve`
uses, same metadata.

Accepts a leading `@` and trailing pandoc-terminator punctuation
(`/`, `.`, `,`, etc.); both are normalized away. Errors return as a
`{"error": ..., "cite_key": ...}` dict rather than crashing the
server, so an agent can recover and explain the failure.

### `scan_project(path, recursive=true)`

Walk a Quarto project directory and return the cite-key inventory
grouped by prefix, plus per-key occurrence locations. Same scan
`quartobot scan` does. Useful when the agent needs to see what's
already cited before proposing a new reference.

### `validate_project(path)`

Run the same pre-flight checks `quartobot validate` runs:
`_quarto.yml` exists and declares `bibliography:`, `project.pre-render`
calls `quartobot resolve --id-mode citation-key`, `references.json` is
in the bibliography list, no duplicate cite keys across files. Returns
the full check list, a `passed` boolean, and the failures separately.
Useful for an agent confirming its edits don't break the manuscript's
CI gate.

## Client setup

All examples assume `quartobot` is on the shell `PATH` (the `uv tool
install` path puts it there). Stdio transport only — no port to
configure, no auth to wire up.

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "quartobot": {
      "command": "quartobot",
      "args": ["mcp"]
    }
  }
}
```

Restart Claude Desktop. The three tools show up under the MCP icon at
the bottom of the chat input. Test with: "use quartobot to resolve
`doi:10.1371/journal.pcbi.1007128`."

### Codex CLI

Codex reads MCP servers from `~/.codex/config.toml`. Append:

```toml
[mcp_servers.quartobot]
command = "quartobot"
args = ["mcp"]
```

Restart any running Codex session. The tools become available to the
agent automatically.

### Gemini Code Assist (VS Code)

Open the workspace's `.vscode/settings.json` (or your user settings)
and add:

```json
{
  "geminicodeassist.mcpServers": {
    "quartobot": {
      "command": "quartobot",
      "args": ["mcp"]
    }
  }
}
```

Reload the window. Gemini sees the tools on its next call.

### Any other MCP client

Same command pattern. The server speaks plain stdio MCP, so any client
that lets you point at a binary works:

```
command: quartobot
args: ["mcp"]
```

## What's not here

- **No write tools.** No `init`, no scaffolding, no auto-write to
  `_quarto.yml`. The cost of a hallucinated citation is small and
  scoped to the agent's reply; the cost of an agent writing a
  scaffold into the wrong directory is not. If MCP grows a
  confirmation-UX primitive that the major clients honor, that
  calculus changes.
- **No HTTP/SSE transport.** Every authoring client that matters
  today is stdio. The MCP spec supports networked transports;
  `quartobot mcp` doesn't, until somebody asks.
- **No `quartobot mcp install <client>` helper.** Each client has its
  own config schema and filesystem layout; chasing the drift on three
  or four moving targets is the kind of maintenance load that
  outweighs the convenience. The snippets above are short enough.
