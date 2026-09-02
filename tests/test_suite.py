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


# ---- pnl_engine.compute: synthetic series (newest-first, as the API) ----
# Day 1: eq 100 (base). Day 2: pnl +40, dep +10 -> eq 150.
# Day 3: pnl +10 (a losing day: Δ-30), withdrawal -30 (cum ntr -20) -> eq 90.
rows = [
    {"createdAt": "2026-01-03T00:00:00Z", "equity": "90", "totalPnl": "10", "netTransfers": "-30"},
    {"createdAt": "2026-01-02T00:00:00Z", "equity": "150", "totalPnl": "40", "netTransfers": "10"},
    {"createdAt": "2026-01-01T00:00:00Z", "equity": "100", "totalPnl": "0", "netTransfers": "0"},
]
s = compute(rows)
ok("identity residual = 0 on synthetic data", s["identity_max_residual_usd"] == 0.0)
ok("totalPnl_now = 10", s["totalPnl_now"] == 10)
ok("equity_now = 90", s["equity_now"] == 90)
ok("netTransfers_window = -20", s["netTransfers_window"] == -20.0)
ok("day_winrate: 1 of 2 days = 50%", s["day_winrate_pct"] == 50.0)
# maxDD on deposit-adjusted equity (perf: 100 -> 140 -> 110): 30/140 = 21.4%
ok("maxDD = 21.43% (deposit-adjusted)", s["max_drawdown_pct"] == 21.43)
rows_dd = [
    {"createdAt": "2026-01-03T00:00:00Z", "equity": "50", "totalPnl": "-50", "netTransfers": "0"},
    {"createdAt": "2026-01-02T00:00:00Z", "equity": "100", "totalPnl": "0", "netTransfers": "0"},
]
ok("maxDD = 50% on a declining series", compute(rows_dd)["max_drawdown_pct"] == 50.0)

# ---- quantize: vectors from live ETH market meta ----
m = {"atomicResolution": -9, "stepBaseQuantums": 1000000,
     "tickSize": "0.1", "subticksPerTick": 100000}
q = quantize(m, 0.05, 2445.5)
ok("quantize size", q["size_quantums"] == 50_000_000)
ok("quantize price", q["price_subticks"] == 2_445_500_000)
q2 = quantize(m, 0.05009, 2445.54)   # below a step -> floor
ok("quantize rounds down to the step", q2["size_quantums"] == 50_000_000)

# ---- bech32/quantize from signer selftest + timestamp invariant ----
sk = SigningKey.generate(curve=SECP256k1)
api_c = sign_api_credentials(sk, timestamp_ms=1700000000000)
ok("signed timestamp == returned timestamp", api_c["timestamp"] == 1700000000000)
ok("key_from_hex: private key 0x01 maps to address 7E5F...5Bdf",
   "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf" == __import__("dydx_mcp.signer", fromlist=["eth_address"]).eth_address(key_from_hex("0x01").get_verifying_key()))

# ---- scanner.valid: bech32 checksum ----
from scanner import valid  # noqa: E402
good = "dydx1m9hg73dtn5ku8ulmj8rjmdqh0hk7uuhawc69cn"
ok("a valid real address passes", valid(good))
ok("a truncated address (42) is rejected", not valid(good[:-1]))
corrupt = good[:-1] + ("a" if good[-1] != "a" else "b")
ok("a broken checksum is rejected", not valid(corrupt))

# ---- alerts: delivered logic (a pure env-check function) ----
import alerts  # noqa: E402
import os  # noqa: E402
saved = {k: os.environ.pop(k, None) for k in
         ("DYDX_TG_BOT_TOKEN", "DYDX_TG_CHAT_ID", "DYDX_WEBHOOKS")}
n = alerts.publish_all()
ok("with no channels configured events stay queued", n == 0)
for k, v in saved.items():
    if v is not None:
        os.environ[k] = v

print()
if FAILURES:
    print(f"TOTAL: {len(FAILURES)} FAIL: {FAILURES}")
    sys.exit(1)
print("TOTAL: all tests passed")
