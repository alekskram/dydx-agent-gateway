"""Block scanner: builds a sqlite registry of active dYdX chain addresses.

Walks dYdX blocks via public RPC, extracts bech32 addresses (dydx1...) from
raw transaction bytes, and upserts them into data/registry.sqlite with
first/last seen and hit counts. High-hit addresses are typically validator
order-committers; low-hit ones are usually real traders (deposits/etc).

Usage:
  python scanner.py --blocks 120      # scan next 120 blocks, then exit
  python scanner.py                   # continuous (for a systemd service later)
"""
import argparse
import base64
import json
import re
import sqlite3
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RPCS = [
    "https://dydx-rpc.publicnode.com/",
    "https://rpc.lavenderfive.com:443/dydx",
    "https://dydx-rpc.polkachu.com:443",
]
ADDR_RE = re.compile(rb"dydx1[a-z0-9]{20,60}")
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
DB = Path(__file__).parent / "data" / "registry.sqlite"


def _polymod(values):
    GEN = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= GEN[i] if ((b >> i) & 1) else 0
    return chk


def valid(addr: str) -> bool:
    """Full bech32 check (BIP-173): hrp dydx, 43 chars, valid checksum."""
    if len(addr) != 43 or not addr.startswith("dydx1"):
        return False
    try:
        data = [BECH32_CHARSET.index(c) for c in addr[5:]]  # after "dydx1"
    except ValueError:
        return False
    expand = [ord(c) >> 5 for c in "dydx"] + [0] + [ord(c) & 31 for c in "dydx"]
    return _polymod(expand + data) == 1


def rpc(method, params, timeout=20):
    last = None
    for base in RPCS:
        req = urllib.request.Request(
            base,
            data=json.dumps({"jsonrpc": "2.0", "id": 1,
                             "method": method, "params": params}).encode(),
            headers={"Content-Type": "application/json",
                     "User-Agent": "dydx-agent-gateway/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001 - try next RPC
            last = e
            time.sleep(0.3)
    raise RuntimeError(f"all RPCs failed: {last}")


def latest_height() -> int:
    return int(rpc("status", {})["result"]["sync_info"]["latest_block_height"])


def block_addresses(height: int) -> set[str]:
    b = rpc("block", {"height": str(height)})
    out = set()
    for txb64 in b["result"]["block"]["data"]["txs"]:
        for m in ADDR_RE.findall(base64.b64decode(txb64)):
            out.add(m.decode())
    return out


def db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")  # safe concurrent reads by MCP
    con.execute("""CREATE TABLE IF NOT EXISTS addresses(
        address TEXT PRIMARY KEY, first_seen TEXT, last_seen TEXT,
        hits INTEGER, last_height INTEGER)""")
    # idempotent (address, block) pairs: rescans after crashes never double-count
    con.execute("""CREATE TABLE IF NOT EXISTS addr_blocks(
        address TEXT, height INTEGER, UNIQUE(address, height))""")
    con.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
    return con


def cursor(con: sqlite3.Connection) -> int:
    row = con.execute("SELECT v FROM meta WHERE k='cursor'").fetchone()
    return int(row[0]) if row else 0


def run(n_blocks: int | None):
    con = db()
    cur = cursor(con)
    tip = latest_height()
    if cur == 0:
        cur = tip - 5 if n_blocks is None else tip - n_blocks
    target = tip if n_blocks is None else min(tip, cur + n_blocks)
    n_addr, n_blocks_done = 0, 0
    while cur < target:
        cur += 1
        try:
            addrs = block_addresses(cur)
        except Exception as e:  # noqa: BLE001 - keep scanning
            print(f"[warn] block {cur}: {e}")
            continue
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for a in addrs:
            if not valid(a):
                continue
            cur2 = con.execute(
                "INSERT OR IGNORE INTO addr_blocks(address, height) VALUES(?,?)",
                (a, cur))
            if cur2.rowcount == 0:
                continue  # already counted for this block
            con.execute("""INSERT INTO addresses(address, first_seen, last_seen, hits, last_height)
                VALUES(?,?,?,1,?)
                ON CONFLICT(address) DO UPDATE SET
                  last_seen=excluded.last_seen, hits=hits+1,
                  last_height=excluded.last_height""", (a, now, now, cur))
        n_addr += len(addrs)
        n_blocks_done += 1
        if n_blocks_done % 20 == 0:
            con.execute("INSERT OR REPLACE INTO meta VALUES('cursor',?)", (str(cur),))
            con.commit()
            print(f"  scanned {n_blocks_done} blocks -> height {cur}, "
                  f"{n_addr} addr-events")
        time.sleep(0.08)  # ~12 blocks/s ceiling, polite to public RPC
    con.execute("INSERT OR REPLACE INTO meta VALUES('cursor',?)", (str(cur),))
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM addresses").fetchone()[0]
    print(f"done: {n_blocks_done} blocks, {n_addr} addr-events; "
          f"registry total {total} addresses -> {DB}")
    top = con.execute("SELECT address, hits FROM addresses "
                      "ORDER BY hits DESC LIMIT 5").fetchall()
    for a, h in top:
        print(f"  top: {a} ({h} hits)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", type=int, default=None)
    args = ap.parse_args()
    run(args.blocks)
