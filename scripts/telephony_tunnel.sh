#!/bin/sh
# Run `make telephony-gateway` in another terminal before this command.
set -eu
project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if command -v cloudflared >/dev/null 2>&1; then
    tunnel_binary=$(command -v cloudflared)
elif [ -x "$project_root/.runtime/bin/cloudflared" ]; then
    tunnel_binary="$project_root/.runtime/bin/cloudflared"
else
    echo 'cloudflared is required; install it or place it in .runtime/bin/cloudflared.' >&2
    exit 1
fi
# A Quick Tunnel creates a temporary HTTPS URL. It forwards only the standalone
# callback gateway; merchant APIs on port 8000 remain outside this tunnel.
exec "$tunnel_binary" tunnel --url http://127.0.0.1:8010 --no-autoupdate
