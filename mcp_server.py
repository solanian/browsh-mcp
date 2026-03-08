"""
browsh-mcp: Browser control MCP server powered by browsh + Firefox CDP.

Architecture:
  - Text rendering: browsh HTTP server (localhost:4333) renders any URL as plain text
  - Browser control: Firefox CDP (localhost:9222) provides click, type, scroll, JS execution
  - MCP transport: stdio (JSON-RPC 2.0)

Tools:
  navigate(url)          - Render a page as plain text via browsh
  snapshot(url?)         - Text snapshot or current session info
  goto(url)              - Navigate browser for interactive use (CDP)
  click(css_selector)    - Click an element
  type_text(selector, text) - Type into an input field
  scroll(direction, amount) - Scroll the page
  press_key(key)         - Press a keyboard key
  get_links(url?)        - Extract all links from a page
  get_page_elements(sel) - List interactive elements
  execute_js(script)     - Run JavaScript and return result
"""

import asyncio
import json
import logging

import httpx
import websockets
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BROWSH_URL = "http://localhost:4333"
CDP_URL = "http://localhost:9222"

mcp = FastMCP(
    "browsh-browser",
    instructions=(
        "Browser control MCP server based on browsh. "
        "Use `navigate` to open a page and get its text rendering. "
        "Use `goto` to move the browser for interactive control. "
        "Use `click`, `type_text`, `scroll`, `press_key`, and `execute_js` "
        "for interactive browser control via CDP."
    ),
)


# ==========================================================================
# CDP (Chrome DevTools Protocol) client
# ==========================================================================

class CDPSession:
    """Minimal async CDP client over WebSocket."""

    def __init__(self):
        self._ws = None
        self._ws_url: str | None = None
        self._msg_id = 0

    async def connect(self) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{CDP_URL}/json/list", timeout=10)
            targets = resp.json()

        ws_url = None
        for t in targets:
            if t.get("type") == "page":
                ws_url = t.get("webSocketDebuggerUrl")
                if ws_url and "about:blank" not in t.get("url", ""):
                    break
        if not ws_url:
            for t in targets:
                ws_url = t.get("webSocketDebuggerUrl")
                if ws_url:
                    break
        if not ws_url:
            raise ConnectionError("No CDP WebSocket target found")

        self._ws_url = ws_url
        self._ws = await websockets.connect(ws_url, max_size=10 * 1024 * 1024)
        await self.send("Page.enable")
        await self.send("Runtime.enable")
        logger.info("CDP connected: %s", ws_url)

    async def send(self, method: str, params: dict | None = None) -> dict:
        self._msg_id += 1
        msg_id = self._msg_id
        await self._ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=30)
            data = json.loads(raw)
            if data.get("id") == msg_id:
                if "error" in data:
                    raise RuntimeError(f"CDP error: {data['error']}")
                return data.get("result", {})

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None


_cdp: CDPSession | None = None


async def _get_cdp() -> CDPSession:
    global _cdp
    if _cdp and _cdp._ws:
        try:
            await _cdp._ws.ping()
            return _cdp
        except Exception:
            pass
    if _cdp:
        try:
            await _cdp.close()
        except Exception:
            pass
    cdp = CDPSession()
    await cdp.connect()
    _cdp = cdp
    return cdp


async def _cdp_eval(expression: str) -> any:
    """Evaluate JS via CDP with auto-reconnect on stale context."""
    global _cdp
    for attempt in range(5):
        cdp = await _get_cdp()
        try:
            result = await cdp.send("Runtime.evaluate", {
                "expression": expression,
                "returnByValue": True,
            })
        except Exception as e:
            logger.info("CDP send failed (attempt %d): %s", attempt + 1, e)
            try:
                await cdp.close()
            except Exception:
                pass
            _cdp = None
            await asyncio.sleep(2)
            continue

        if "exceptionDetails" in result:
            if "context is null" in str(result):
                logger.info("Stale CDP context, reconnecting (attempt %d)", attempt + 1)
                try:
                    await cdp.close()
                except Exception:
                    pass
                _cdp = None
                await asyncio.sleep(2)
                continue
            exc = result["exceptionDetails"]
            text = exc.get("text", "") or exc.get("exception", {}).get("description", "error")
            raise RuntimeError(f"JS error: {text}")

        return result.get("result", {}).get("value")

    raise RuntimeError("CDP context unavailable after 5 attempts")


async def _cdp_navigate(url: str) -> None:
    """Navigate via CDP and reconnect for fresh context."""
    global _cdp
    cdp = await _get_cdp()
    await cdp.send("Page.navigate", {"url": url})
    await asyncio.sleep(2)
    try:
        await cdp.close()
    except Exception:
        pass
    _cdp = None

    for attempt in range(8):
        try:
            await _get_cdp()
            await _cdp_eval("1+1")
            return
        except Exception:
            _cdp = None
            await asyncio.sleep(1)


# ==========================================================================
# Tools — Text rendering (browsh)
# ==========================================================================

@mcp.tool()
async def navigate(url: str, columns: int = 200, render_delay: int = 2000) -> str:
    """Render a web page as plain text via browsh.

    Args:
        url: URL to visit (e.g. "https://example.com")
        columns: Terminal width for text rendering (default 200)
        render_delay: Milliseconds to wait for JS rendering (default 2000)
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            f"{BROWSH_URL}/{url}",
            headers={"X-Browsh-Raw-Mode": "PLAIN"},
            params={"columns": str(columns), "render_delay": str(render_delay)},
        )
        resp.raise_for_status()

    text = resp.text.strip()
    if not text:
        return f"[No text content rendered for {url}]"
    lines = text.split("\n")
    if len(lines) > 500:
        text = "\n".join(lines[:500]) + f"\n\n[... truncated, {len(lines)} total lines]"
    return f"=== {url} ===\n\n{text}"


@mcp.tool()
async def snapshot(url: str = "", columns: int = 200, render_delay: int = 1000) -> str:
    """Get a text snapshot of a page, or show current session info if no URL given.

    Args:
        url: URL to snapshot (empty = current session info)
        columns: Terminal width
        render_delay: Render wait time in ms
    """
    if url:
        return await navigate(url, columns, render_delay)
    try:
        title = await _cdp_eval("document.title")
        cur = await _cdp_eval("window.location.href")
        return f"Current page: {title}\nURL: {cur}"
    except Exception as e:
        return f"No URL provided and CDP unavailable: {e}"


# ==========================================================================
# Tools — Browser interaction (CDP)
# ==========================================================================

@mcp.tool()
async def goto(url: str) -> str:
    """Navigate the browser to a URL for interactive control.

    Use this before click/type/scroll. Unlike `navigate`, this does NOT
    return page text — use `navigate` or `snapshot` for that.

    Args:
        url: URL to navigate to
    """
    try:
        full_url = url if url.startswith(("http://", "https://")) else "https://" + url
        await _cdp_navigate(full_url)
        title = await _cdp_eval("document.title")
        cur = await _cdp_eval("window.location.href")
        return f"Navigated to: {cur}\nTitle: {title}"
    except Exception as e:
        return f"Error navigating to {url}: {e}"


@mcp.tool()
async def click(css_selector: str) -> str:
    """Click an element by CSS selector.

    Args:
        css_selector: e.g. "button.submit", "#login", "a[href='/about']"
    """
    try:
        result = await _cdp_eval(f"""
            (() => {{
                const el = document.querySelector('{css_selector}');
                if (!el) return 'Element not found: {css_selector}';
                el.scrollIntoView({{block: 'center'}});
                el.click();
                return 'Clicked: {css_selector}';
            }})()
        """)
        return str(result)
    except Exception as e:
        return f"Error clicking '{css_selector}': {e}"


@mcp.tool()
async def type_text(css_selector: str, text: str, clear_first: bool = True) -> str:
    """Type text into an input field.

    Args:
        css_selector: CSS selector for the input element
        text: Text to type
        clear_first: Clear existing value first (default True)
    """
    try:
        js_text = json.dumps(text)
        clear_js = "el.value = '';" if clear_first else ""
        result = await _cdp_eval(f"""
            (() => {{
                const el = document.querySelector('{css_selector}');
                if (!el) return 'Element not found: {css_selector}';
                el.focus();
                {clear_js}
                el.value = {js_text};
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
                return 'Typed into: {css_selector}';
            }})()
        """)
        return str(result)
    except Exception as e:
        return f"Error typing into '{css_selector}': {e}"


@mcp.tool()
async def scroll(direction: str = "down", amount: int = 500) -> str:
    """Scroll the page.

    Args:
        direction: "up", "down", "left", or "right"
        amount: Pixels to scroll (default 500)
    """
    dx, dy = 0, 0
    match direction.lower():
        case "down": dy = amount
        case "up": dy = -amount
        case "right": dx = amount
        case "left": dx = -amount
        case _: return f"Unknown direction: {direction}. Use up/down/left/right."
    try:
        await _cdp_eval(f"window.scrollBy({dx}, {dy})")
        return f"Scrolled {direction} by {amount}px"
    except Exception as e:
        return f"Error scrolling: {e}"


@mcp.tool()
async def press_key(key: str) -> str:
    """Press a keyboard key.

    Args:
        key: Key name — Enter, Tab, Escape, Backspace, ArrowUp, ArrowDown, Space, etc.
    """
    key_defs = {
        "enter": ("Enter", "Enter", 13), "return": ("Enter", "Enter", 13),
        "tab": ("Tab", "Tab", 9), "escape": ("Escape", "Escape", 27),
        "esc": ("Escape", "Escape", 27), "backspace": ("Backspace", "Backspace", 8),
        "delete": ("Delete", "Delete", 46), "space": (" ", "Space", 32),
        "arrowup": ("ArrowUp", "ArrowUp", 38), "arrowdown": ("ArrowDown", "ArrowDown", 40),
        "arrowleft": ("ArrowLeft", "ArrowLeft", 37), "arrowright": ("ArrowRight", "ArrowRight", 39),
        "home": ("Home", "Home", 36), "end": ("End", "End", 35),
        "pageup": ("PageUp", "PageUp", 33), "pagedown": ("PageDown", "PageDown", 34),
    }
    k = key_defs.get(key.lower())
    kn, kc, kv = k if k else (key, f"Key{key.upper()}", ord(key.upper()))
    try:
        cdp = await _get_cdp()
        for etype in ("keyDown", "keyUp"):
            await cdp.send("Input.dispatchKeyEvent", {
                "type": etype, "key": kn, "code": kc,
                "windowsVirtualKeyCode": kv, "nativeVirtualKeyCode": kv,
            })
        return f"Pressed key: {key}"
    except Exception as e:
        return f"Error pressing key '{key}': {e}"


@mcp.tool()
async def get_links(url: str = "") -> str:
    """Extract all links from the current page (or navigate first).

    Args:
        url: Optional URL to navigate to before extracting links.
    """
    if url:
        full_url = url if url.startswith(("http://", "https://")) else "https://" + url
        await _cdp_navigate(full_url)
        await asyncio.sleep(2)
    try:
        links = await _cdp_eval("""
            (() => {
                const out = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    const text = (a.textContent || '').trim().substring(0, 100);
                    if (a.href && text) out.push(text + ' -> ' + a.href);
                });
                return out.slice(0, 200);
            })()
        """)
        if not links:
            return "No links found on the page."
        return f"Found {len(links)} links:\n\n" + "\n".join(links)
    except Exception as e:
        return f"Error getting links: {e}"


@mcp.tool()
async def get_page_elements(css_selector: str = "input, button, a, select, textarea") -> str:
    """List interactive elements on the current page.

    Args:
        css_selector: CSS selector to match (default: form elements + links)
    """
    try:
        sel = json.dumps(css_selector)
        elems = await _cdp_eval(f"""
            (() => {{
                const out = [];
                document.querySelectorAll({sel}).forEach((el, i) => {{
                    const tag = el.tagName.toLowerCase();
                    const type = el.type ? '(' + el.type + ')' : '';
                    const id = el.id ? '#' + el.id : '';
                    const cls = el.className ? '.' + String(el.className).split(' ').join('.') : '';
                    const name = el.name ? '[name=' + el.name + ']' : '';
                    const text = (el.textContent || el.value || el.placeholder || '').trim().substring(0, 60);
                    const href = el.href ? ' href=' + el.href : '';
                    out.push(i + ': <' + tag + type + '> ' + id + cls + name + ' "' + text + '"' + href);
                }});
                return out.slice(0, 100);
            }})()
        """)
        if not elems:
            return f"No elements found matching '{css_selector}'"
        return f"Found {len(elems)} elements:\n\n" + "\n".join(elems)
    except Exception as e:
        return f"Error finding elements: {e}"


@mcp.tool()
async def execute_js(script: str) -> str:
    """Execute JavaScript in the browser and return the result.

    Args:
        script: JS code. Use 'return ...' to get a value back.
    """
    try:
        expr = f"(() => {{ {script} }})()" if "return " in script else script
        value = await _cdp_eval(expr)
        if value is None:
            return "Script executed (no return value)"
        return f"Result: {json.dumps(value, ensure_ascii=False, default=str)}"
    except Exception as e:
        return f"Error executing script: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
