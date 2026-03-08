#!/bin/bash
set -e

# Start Xvfb (virtual display for Firefox)
export DISPLAY=:99
Xvfb :99 -screen 0 1920x1080x24 -ac &>/dev/null &
sleep 2

# browsh will use our wrapper via --firefox.path.
# The wrapper injects --remote-debugging-port for CDP access alongside Marionette.
cat > /tmp/firefox-cdp-wrapper << 'WRAPPER'
#!/bin/bash
exec /usr/bin/firefox-esr --remote-debugging-port=9222 "$@"
WRAPPER
chmod +x /tmp/firefox-cdp-wrapper

# Start browsh in HTTP server mode with our wrapper
/app/bin/browsh --http-server-mode --firefox.path /tmp/firefox-cdp-wrapper &>/dev/null &
BROWSH_PID=$!

# Wait for CDP to be ready (port 9222)
echo "Waiting for Firefox CDP (port 9222)..." >&2
for i in $(seq 1 60); do
    if curl -s http://localhost:9222/json/version >/dev/null 2>&1; then
        echo "CDP is ready (after ${i}s)" >&2
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "WARNING: CDP not detected after 60s" >&2
    fi
    sleep 1
done

# Wait for browsh HTTP server to be ready
echo "Waiting for browsh HTTP server (port 4333)..." >&2
for i in $(seq 1 30); do
    if curl -s http://localhost:4333/ > /dev/null 2>&1; then
        echo "browsh HTTP server is ready (after ${i}s)" >&2
        break
    fi
    sleep 1
done

echo "All services started (browsh=$BROWSH_PID)" >&2

# Start MCP server (stdio)
exec python3 /app/mcp_server.py
