# Публичный URL шлюза через Cloudflare Tunnel

На сервере cloudflared уже установлен и работает (юнит cloudflared-coffee
подтверждает outbound до Cloudflare). Осталось создать ИМЕНОВАННЫЙ туннель —
быстрые trycloudflare-URL не подходят (умирают при рестарте).

## Шаги (один раз, ~15 минут, нужны: Cloudflare-аккаунт + домен)

1. Cloudflare Dashboard → Zero Trust → Networks → Tunnels → Create tunnel
   → тип Cloudflared → имя `dydx-gateway` → скопировать токен.
2. На сервере:
   ```bash
   systemctl edit --force --full dydx-tunnel  # или просто файл ниже
   ```
   `/etc/systemd/system/dydx-tunnel.service`:
   ```ini
   [Unit]
   Description=Cloudflare Tunnel for dydx-agent-gateway
   After=network-online.target
   [Service]
   ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate run \
     --token ВСТАВЬ_ТОКЕН
   Restart=always
   [Install]
   WantedBy=multi-user.target
   ```
3. В настройках туннеля (dashboard) → Public Hostname:
   - subdomain: `dydx` (ваш домен), service: `http://localhost:8901`
4. `systemctl enable --now dydx-tunnel`
5. Проверка: любой MCP-клиент → `{"mcpServers":{"dydx":{"type":"http",
   "url":"https://dydx.вашдомен/mcp"}}}`

## Безопасность перед открытием

- Транспорт TLS от Cloudflare; origin остаётся 127.0.0.1.
- **Origin/Host-валидация на стороне fastmcp** (требование спеки MCP для
  Streamable HTTP): при запуске передать `allowed_hosts=["dydx.домен"]`,
  `allowed_origins=[...]` (анти-DNS-rebinding); за балансировщиком —
  stateless-режим.
- **/health** — незашифрованный JSON-эндпоинт уже вшит в сервер
  (`custom_route`), пригоден для Cloudflare health checks и мониторинга.
- Для человеческих страниц (будущий лидерборд) — Cloudflare Access (email
  OTP) бесплатен до 50 пользователей.
- Для агентского MCP-URL: read-only инструменты могут работать без auth;
  при включении чувствительных функций —
  Service Token через Access или OAuth 2.1 resource server по спеке
  (RFC 9728 metadata + WWW-Authenticate на 401).
- Cloudflare скрывает IP сервера; rate-limit правилом 100 req/10s/IP на
  пути `/mcp` — зеркалит наш внутренний лимит.

## Стоимость

Туннель — бесплатен. Нужен только домен в Cloudflare DNS (от ~$10/год, или
бесплатный поддомен существующего домена пользователя).
