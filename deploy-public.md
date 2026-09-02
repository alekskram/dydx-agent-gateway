# Public gateway URL via Cloudflare Tunnel

cloudflared is already installed and running on the server (the
cloudflared-coffee unit confirms outbound connectivity to Cloudflare).
What remains is to create a NAMED tunnel — quick trycloudflare URLs will
not do (they die on restart).

## Steps (once, ~15 minutes; requires: a Cloudflare account + a domain)

1. Cloudflare Dashboard → Zero Trust → Networks → Tunnels → Create tunnel
   → type Cloudflared → name `dydx-gateway` → copy the token.
2. On the server:
   ```bash
   systemctl edit --force --full dydx-tunnel  # or just use the file below
   ```
   `/etc/systemd/system/dydx-tunnel.service`:
   ```ini
   [Unit]
   Description=Cloudflare Tunnel for dydx-agent-gateway
   After=network-online.target
   [Service]
   ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate run \
     --token PASTE_TOKEN
   Restart=always
   [Install]
   WantedBy=multi-user.target
   ```
3. In the tunnel settings (dashboard) → Public Hostname:
   - subdomain: `dydx` (your domain), service: `http://localhost:8901`
4. `systemctl enable --now dydx-tunnel`
5. Verify: any MCP client → `{"mcpServers":{"dydx":{"type":"http",
   "url":"https://dydx.yourdomain/mcp"}}}`

## Security before going public

- TLS transport terminates at Cloudflare; the origin stays on 127.0.0.1.
- **Origin/Host validation on the fastmcp side** (an MCP spec requirement
  for Streamable HTTP): pass `allowed_hosts=["dydx.domain"]` and
  `allowed_origins=[...]` at startup (anti-DNS-rebinding); behind a load
  balancer — stateless mode.
- **/health** — a plain JSON endpoint is already built into the server
  (`custom_route`); suitable for Cloudflare health checks and monitoring.
- For human-facing pages (a future leaderboard) — Cloudflare Access
  (email OTP) is free up to 50 users.
- For the agent-facing MCP URL: read-only tools can work without auth;
  once sensitive features are enabled — a Service Token via Access, or an
  OAuth 2.1 resource server per spec (RFC 9728 metadata +
  WWW-Authenticate on 401).
- Cloudflare hides the server IP; add a rate-limit rule of
  100 req/10s/IP on the `/mcp` path — mirrors our internal cap.

## Cost

The tunnel is free. You only need a domain on Cloudflare DNS (from
~$10/year, or a free subdomain of an existing domain).
