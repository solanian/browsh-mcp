# browsh-mcp

**[English](README.md)** | **[한국어](README_KO.md)**

A Docker-based MCP server that gives AI agents a real web browser. Uses [browsh](https://www.brow.sh/) for text rendering and Firefox CDP for interactive control — no vision model needed.

## What it does

| Capability | How | Tools |
|------------|-----|-------|
| **Read web pages as text** | browsh renders full JS pages as plain text | `navigate`, `snapshot` |
| **Control the browser** | Firefox CDP (click, type, scroll) | `goto`, `click`, `type_text`, `scroll`, `press_key` |
| **Extract page data** | CDP JavaScript execution | `get_links`, `get_page_elements`, `execute_js` |

## Quick Start

**Copy the prompt below and paste it into your AI coding agent.** The agent will build the Docker image, ask which client you want to configure, and set everything up for you.

### Setup Prompt

```
Read the README.md in this repository to understand browsh-mcp, then help me set it up.

1. Build the Docker image by running: docker build -t browsh-mcp .
2. Ask me which AI client I want to configure the MCP server for. Options:
   - Claude Code
   - OpenAI Codex CLI
   - Google Gemini CLI (Antigravity)
   - opencode
3. Based on my choice, follow the matching setup guide in the README to configure the MCP server.
4. After setup, verify the server works by running:
   echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | timeout 60 docker run -i --rm browsh-mcp 2>/dev/null
5. Confirm the result contains serverInfo.name: "browsh-browser", then let me know setup is complete.
```

---

## Setup Guide by AI Client

<details>
<summary><b>Claude Code</b></summary>

Add to `~/.claude/mcp_servers.json` (global) or `.mcp.json` (per-project):

```json
{
  "mcpServers": {
    "browser": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "browsh-mcp"]
    }
  }
}
```

Restart Claude Code. The `browser` tools will appear automatically.

</details>

<details>
<summary><b>OpenAI Codex (CLI)</b></summary>

Add to `~/.codex/config.json`:

```json
{
  "mcpServers": {
    "browser": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "browsh-mcp"]
    }
  }
}
```

Or pass directly via CLI flag:

```bash
codex --mcp-server "docker run -i --rm browsh-mcp"
```

</details>

<details>
<summary><b>Google Gemini CLI (Antigravity)</b></summary>

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "browser": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "browsh-mcp"]
    }
  }
}
```

</details>

<details>
<summary><b>opencode</b></summary>

Add to `.opencode/config.json` or `~/.opencode/config.json`:

```json
{
  "mcpServers": {
    "browser": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "browsh-mcp"]
    }
  }
}
```

Or add via CLI:

```bash
opencode mcp add browser -- docker run -i --rm browsh-mcp
```

</details>

<details>
<summary><b>Generic MCP Client (any language)</b></summary>

The server communicates via **stdio** (JSON-RPC 2.0). Start the container and pipe JSON-RPC messages to stdin:

```bash
# Start container with stdin open
docker run -i --rm browsh-mcp

# Send on stdin (line-delimited JSON-RPC):
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"my-app","version":"1.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"navigate","arguments":{"url":"https://example.com"}}}
```

</details>

---

## Tools Reference

### Text Rendering (browsh)

| Tool | Description | Key Args |
|------|-------------|----------|
| `navigate(url)` | Open URL, return page as plain text | `url`, `columns=200`, `render_delay=2000` |
| `snapshot(url?)` | Same as navigate, or show current session | `url` (optional) |

### Browser Control (CDP)

| Tool | Description | Key Args |
|------|-------------|----------|
| `goto(url)` | Navigate browser for interaction (no text returned) | `url` |
| `click(selector)` | Click an element | `css_selector` |
| `type_text(selector, text)` | Type into an input field | `css_selector`, `text`, `clear_first=true` |
| `scroll(direction)` | Scroll the page | `direction` (up/down/left/right), `amount=500` |
| `press_key(key)` | Press a key | `key` (Enter, Tab, Escape, ArrowDown, etc.) |

### Page Analysis (CDP)

| Tool | Description | Key Args |
|------|-------------|----------|
| `get_links(url?)` | List all links on the page | `url` (optional) |
| `get_page_elements(sel?)` | List interactive elements | `css_selector` (default: inputs, buttons, links) |
| `execute_js(script)` | Run JavaScript, return result | `script` (use `return` for values) |

### Typical workflow

```
1. navigate("https://site.com")      → read the page as text
2. goto("https://site.com")          → prepare for interaction
3. get_page_elements()               → see available inputs/buttons
4. type_text("input[name=q]", "AI")  → fill a search box
5. press_key("Enter")                → submit
6. navigate("https://site.com/results") → read the results as text
```

---

## Architecture

```
┌──────────────────────────────────────────┐
│  Docker Container                        │
│                                          │
│  Xvfb (:99)  →  Firefox ESR             │
│                  ├─ Marionette → browsh  │
│                  └─ CDP :9222  → MCP srv │
│                                          │
│  browsh HTTP :4333  ← text rendering     │
│  MCP server (stdio) ← AI client         │
│       ▲         │                        │
│  stdin │         │ stdout                │
└────────┼─────────┼───────────────────────┘
         │         ▼
     AI Agent (Claude, Codex, Gemini, etc.)
```

- **browsh** manages Firefox via Marionette, renders pages as text
- **CDP** (Chrome DevTools Protocol) on the same Firefox provides interactive control
- **MCP server** bridges both via stdio JSON-RPC

## Notes

- First `navigate` call may be slow (~30s) due to Firefox cold start. Subsequent calls are fast.
- X/Twitter requires login — use trend aggregators like `trends24.in` or `getdaytrends.com` instead.
- Container size: ~370MB (compressed), ~1.4GB (on disk).
- Runs as non-root user inside the container.

## License

MIT
