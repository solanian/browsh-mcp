# browsh-mcp

**[English](README.md)** | **[한국어](README_KO.md)**

AI 에이전트에게 실제 웹 브라우저를 제공하는 Docker 기반 MCP 서버입니다. [browsh](https://www.brow.sh/)로 텍스트 렌더링, Firefox CDP로 인터랙티브 제어 — 비전 모델이 필요 없습니다.

## 주요 기능

| 기능 | 방식 | 도구 |
|------|------|------|
| **웹 페이지를 텍스트로 읽기** | browsh가 JS 페이지를 일반 텍스트로 렌더링 | `navigate`, `snapshot` |
| **브라우저 제어** | Firefox CDP (클릭, 타이핑, 스크롤) | `goto`, `click`, `type_text`, `scroll`, `press_key` |
| **페이지 데이터 추출** | CDP JavaScript 실행 | `get_links`, `get_page_elements`, `execute_js` |

## 빠른 시작

### 1. 이미지 빌드

```bash
docker build -t browsh-mcp .
```

### 2. 동작 확인

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \
  | timeout 60 docker run -i --rm browsh-mcp 2>/dev/null
```

`serverInfo.name: "browsh-browser"`가 포함된 JSON 응답이 표시되면 정상입니다.

### 3. AI 에이전트에 연결 (아래 참조)

---

## AI 클라이언트별 설정 가이드

### Claude Code

`~/.claude/mcp_servers.json` (전역) 또는 `.mcp.json` (프로젝트별)에 추가:

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

Claude Code를 재시작하면 `browser` 도구가 자동으로 나타납니다.

**사용 예시:**
```
> Use the browser MCP to search Google News for "AI regulation 2026" and summarize the top results.
```

---

### OpenAI Codex (CLI)

Codex는 설정 파일을 통해 MCP 서버를 지원합니다. `~/.codex/config.json`에 추가:

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

또는 CLI 플래그로 직접 전달:

```bash
codex --mcp-server "docker run -i --rm browsh-mcp"
```

**사용 예시:**
```
> Browse https://news.ycombinator.com and list the top 10 posts using the browser MCP.
```

---

### Google Gemini CLI (Antigravity)

`~/.gemini/settings.json`에 MCP 서버 추가:

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

**사용 예시:**
```
> Use the browser tool to navigate to https://trends24.in and get today's trending topics.
```

---

### opencode

프로젝트의 `.opencode/config.json` 또는 `~/.opencode/config.json`에 추가:

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

또는 CLI로 추가:

```bash
opencode mcp add browser -- docker run -i --rm browsh-mcp
```

**사용 예시:**
```
> Use the browser MCP to go to https://getdaytrends.com and list today's trending topics.
```

---

### 일반 MCP 클라이언트 (모든 언어)

서버는 **stdio** (JSON-RPC 2.0)로 통신합니다. 컨테이너를 시작하고 stdin으로 JSON-RPC 메시지를 전송하세요:

```bash
# stdin을 열고 컨테이너 시작
docker run -i --rm browsh-mcp

# stdin으로 전송 (줄 구분 JSON-RPC):
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"my-app","version":"1.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"navigate","arguments":{"url":"https://example.com"}}}
```

---

## 도구 레퍼런스

### 텍스트 렌더링 (browsh)

| 도구 | 설명 | 주요 인자 |
|------|------|-----------|
| `navigate(url)` | URL을 열고 페이지를 일반 텍스트로 반환 | `url`, `columns=200`, `render_delay=2000` |
| `snapshot(url?)` | navigate와 동일, 또는 현재 세션 표시 | `url` (선택사항) |

### 브라우저 제어 (CDP)

| 도구 | 설명 | 주요 인자 |
|------|------|-----------|
| `goto(url)` | 인터랙션을 위해 브라우저 이동 (텍스트 미반환) | `url` |
| `click(selector)` | 요소 클릭 | `css_selector` |
| `type_text(selector, text)` | 입력 필드에 텍스트 입력 | `css_selector`, `text`, `clear_first=true` |
| `scroll(direction)` | 페이지 스크롤 | `direction` (up/down/left/right), `amount=500` |
| `press_key(key)` | 키 입력 | `key` (Enter, Tab, Escape, ArrowDown 등) |

### 페이지 분석 (CDP)

| 도구 | 설명 | 주요 인자 |
|------|------|-----------|
| `get_links(url?)` | 페이지의 모든 링크 목록 | `url` (선택사항) |
| `get_page_elements(sel?)` | 인터랙티브 요소 목록 | `css_selector` (기본: 입력, 버튼, 링크) |
| `execute_js(script)` | JavaScript 실행 후 결과 반환 | `script` (값 반환 시 `return` 사용) |

### 일반적인 워크플로우

```
1. navigate("https://site.com")      → 페이지를 텍스트로 읽기
2. goto("https://site.com")          → 인터랙션 준비
3. get_page_elements()               → 사용 가능한 입력/버튼 확인
4. type_text("input[name=q]", "AI")  → 검색창에 입력
5. press_key("Enter")                → 제출
6. navigate("https://site.com/results") → 결과를 텍스트로 읽기
```

---

## 아키텍처

```
┌──────────────────────────────────────────┐
│  Docker Container                        │
│                                          │
│  Xvfb (:99)  →  Firefox ESR             │
│                  ├─ Marionette → browsh  │
│                  └─ CDP :9222  → MCP srv │
│                                          │
│  browsh HTTP :4333  ← 텍스트 렌더링      │
│  MCP server (stdio) ← AI 클라이언트     │
│       ▲         │                        │
│  stdin │         │ stdout                │
└────────┼─────────┼───────────────────────┘
         │         ▼
     AI Agent (Claude, Codex, Gemini 등)
```

- **browsh**는 Marionette를 통해 Firefox를 관리하고, 페이지를 텍스트로 렌더링합니다
- **CDP** (Chrome DevTools Protocol)는 동일한 Firefox에서 인터랙티브 제어를 제공합니다
- **MCP 서버**는 stdio JSON-RPC를 통해 두 기능을 연결합니다

## 참고사항

- 첫 `navigate` 호출은 Firefox 콜드 스타트로 인해 느릴 수 있습니다 (~30초). 이후 호출은 빠릅니다.
- X/Twitter는 로그인이 필요합니다 — 대신 `trends24.in`이나 `getdaytrends.com` 같은 트렌드 수집 사이트를 이용하세요.
- 컨테이너 크기: ~370MB (압축), ~1.4GB (디스크).
- 컨테이너 내에서 non-root 사용자로 실행됩니다.

## 라이선스

MIT
