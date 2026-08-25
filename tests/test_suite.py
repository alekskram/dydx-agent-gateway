"""Offline legacy suite (kept runnable without pytest). Isolated from
production data via DYDX_GATEWAY_DATA -> temp dir (set before imports)."""
import os as _os
import tempfile as _tf

_TMP = _tf.mkdtemp(prefix="dydx-legacy-")
_os.environ["DYDX_GATEWAY_DATA"] = _TMP

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dydx_mcp.pnl_engine import compute  # noqa: E402
from dydx_mcp.signer import quantize, sign_api_credentials, key_from_hex  # noqa: E402
from dydx_mcp.signer import SigningKey as _SK  # noqa: E402
from dydx_mcp.signer import SigningKey, SECP256k1  # noqa: E402

FAILURES = []


def ok(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        FAILURES.append(name)


# ---- pnl_engine.compute: синтетический ряд (newest-first, как API) ----
# День 1: eq 100 (база). День 2: pnl +40, деп +10 -> eq 150.
# День 3: pnl +10 (день убыточный: Δ-30), вывод -30 (cum ntr -20) -> eq 90.
rows = [
    {"createdAt": "2026-01-03T00:00:00Z", "equity": "90", "totalPnl": "10", "netTransfers": "-30"},
    {"createdAt": "2026-01-02T00:00:00Z", "equity": "150", "totalPnl": "40", "netTransfers": "10"},
    {"createdAt": "2026-01-01T00:00:00Z", "equity": "100", "totalPnl": "0", "netTransfers": "0"},
]
s = compute(rows)
ok("identity residual = 0 на синтетике", s["identity_max_residual_usd"] == 0.0)
ok("totalPnl_now = 10", s["totalPnl_now"] == 10)
ok("equity_now = 90", s["equity_now"] == 90)
ok("netTransfers_window = -20", s["netTransfers_window"] == -20.0)
ok("day_winrate: 1 из 2 дней = 50%", s["day_winrate_pct"] == 50.0)
# maxDD на депозит-скорр. (perf: 100 -> 140 -> 110): 30/140 = 21.4%
ok("maxDD = 21.43% (депозит-скорр.)", s["max_drawdown_pct"] == 21.43)
rows_dd = [
    {"createdAt": "2026-01-03T00:00:00Z", "equity": "50", "totalPnl": "-50", "netTransfers": "0"},
    {"createdAt": "2026-01-02T00:00:00Z", "equity": "100", "totalPnl": "0", "netTransfers": "0"},
]
ok("maxDD = 50% на падающей синтетике", compute(rows_dd)["max_drawdown_pct"] == 50.0)

# ---- quantize: векторы из живой меты ETH ----
m = {"atomicResolution": -9, "stepBaseQuantums": 1000000,
     "tickSize": "0.1", "subticksPerTick": 100000}
q = quantize(m, 0.05, 2445.5)
ok("quantize size", q["size_quantums"] == 50_000_000)
ok("quantize price", q["price_subticks"] == 2_445_500_000)
q2 = quantize(m, 0.05009, 2445.54)   # ниже шага -> floor
ok("quantize округление к шагу", q2["size_quantums"] == 50_000_000)

# ---- bech32/quantize из signer selftest + timestamp-инвариант ----
sk = SigningKey.generate(curve=SECP256k1)
api_c = sign_api_credentials(sk, timestamp_ms=1700000000000)
ok("подписанный timestamp == возвращённому", api_c["timestamp"] == 1700000000000)
ok("key_from_hex: приватный ключ 0x01 соответствует адресу 7E5F...5Bdf",
   "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf" == __import__("dydx_mcp.signer", fromlist=["eth_address"]).eth_address(key_from_hex("0x01").get_verifying_key()))

# ---- scanner.valid: контрольная сумма bech32 ----
from scanner import valid  # noqa: E402
good = "dydx1m9hg73dtn5ku8ulmj8rjmdqh0hk7uuhawc69cn"
ok("валидный реальный адрес проходит", valid(good))
ok("обрезанный адрес (42) отклоняется", not valid(good[:-1]))
corrupt = good[:-1] + ("a" if good[-1] != "a" else "b")
ok("битая контрольная сумма отклоняется", not valid(corrupt))

# ---- alerts: логика delivered (чистая функция-проверка окружения) ----
import alerts  # noqa: E402
import os  # noqa: E402
saved = {k: os.environ.pop(k, None) for k in
         ("DYDX_TG_BOT_TOKEN", "DYDX_TG_CHAT_ID", "DYDX_WEBHOOKS")}
n = alerts.publish_all()
ok("без настроенных каналов события остаются в очереди", n == 0)
for k, v in saved.items():
    if v is not None:
        os.environ[k] = v

print()
if FAILURES:
    print(f"ИТОГ: {len(FAILURES)} FAIL: {FAILURES}")
    sys.exit(1)
print("ИТОГ: все тесты пройдены")
