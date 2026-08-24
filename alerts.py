"""Alerts: publish unpublished events to Telegram + registered webhooks.

Env: DYDX_TG_BOT_TOKEN + DYDX_TG_CHAT_ID (Telegram),
     DYDX_WEBHOOKS="https://a/hook,https://b/hook" (comma-separated).
Without env set, events stay queued (published=0) — nothing is lost.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dydx_mcp import analytics  # noqa: E402


def tg_send(text: str) -> bool:
    tok, chat = os.environ.get("DYDX_TG_BOT_TOKEN"), os.environ.get("DYDX_TG_CHAT_ID")
    if not (tok and chat):
        return False
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{tok}/sendMessage",
        data=json.dumps({"chat_id": chat, "text": text[:4000]}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def webhook_send(url: str, payload: dict) -> bool:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return 200 <= r.status < 300
    except Exception:  # noqa: BLE001
        return False


def publish_all() -> int:
    hooks = [u for u in os.environ.get("DYDX_WEBHOOKS", "").split(",") if u]
    con = analytics.con()
    rows = con.execute("SELECT * FROM events WHERE published=0 ORDER BY id").fetchall()
    n = 0
    for r in rows:
        p = json.loads(r["payload"])
        text = f"⚠️ {r['kind']} {r['subject']}: {json.dumps(p, ensure_ascii=False)[:300]}"
        tg_configured = bool(os.environ.get("DYDX_TG_BOT_TOKEN")
                             and os.environ.get("DYDX_TG_CHAT_ID"))
        tg_ok = tg_send(text) if tg_configured else True
        hooks_ok = True
        for u in hooks:
            if not webhook_send(u, {"kind": r["kind"], "subject": r["subject"],
                                    "payload": p, "ts": r["ts"]}):
                hooks_ok = False
        delivered = (tg_ok and hooks_ok) and (tg_configured or hooks)
        if delivered:
            con.execute("UPDATE events SET published=1 WHERE id=?", (r["id"],))
            n += 1
    con.commit()
    con.close()
    return n


if __name__ == "__main__":
    print("published:", publish_all())
