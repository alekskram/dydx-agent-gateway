"""Registry access for MCP tools: the sqlite that dydx-scanner fills.

Read-only (WAL mode set by the scanner), so the MCP server and the scanner
service share the file safely.
"""
import sqlite3
import time
from pathlib import Path

DB = Path(__file__).parent.parent / "data" / "registry.sqlite"


def _con() -> sqlite3.Connection:
    # normal (not ro) connection: WAL readers need -shm/-wal access anyway;
    # tools only run SELECTs.
    con = sqlite3.connect(DB, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def stats() -> dict:
    if not DB.exists():  # installed copy without our scanner running
        return {"note": "address registry not built on this host "
                        "(block scanner is a repo extra, not in the pip wheel); "
                        "market/trader tools work via the public indexer"}
    with _con() as con:
        total = con.execute("SELECT COUNT(*) FROM addresses").fetchone()[0]
        cursor = con.execute("SELECT v FROM meta WHERE k='cursor'").fetchone()
        fresh = con.execute(
            "SELECT COUNT(*) FROM addresses WHERE last_seen > datetime('now','-1 day')"
        ).fetchone()[0]
    return {"addresses_total": total, "scanned_up_to_height": int(cursor[0]) if cursor else None,
            "seen_last_24h": fresh, "db": str(DB)}


def recent(limit: int = 10, max_hits: int = 100) -> list[dict]:
    """Recently active addresses, excluding high-frequency committers
    (validators' order-commit blocks inflate hits)."""
    if not DB.exists():
        return []
    with _con() as con:
        rows = con.execute(
            "SELECT address, hits, first_seen, last_seen, last_height "
            "FROM addresses WHERE hits <= ? ORDER BY last_height DESC LIMIT ?",
            (max_hits, limit)).fetchall()
    return [dict(r) for r in rows]


def discover(limit: int = 5, min_equity: float = 100.0,
             probe_max: int = 15, max_hits: int = 100) -> list[dict]:
    """Screener: take recent candidate addresses from the registry and probe
    the indexer for live equity; return funded ones (real active traders)."""
    from . import api
    cands = recent(probe_max, max_hits)
    out = []
    for c in cands:
        try:
            acct = api.account(c["address"])
        except Exception:  # noqa: BLE001 - skip broken probes politely
            continue
        for sub in acct.get("subaccounts", []):
            eq = float(sub.get("equity", 0) or 0)
            if eq >= min_equity:
                out.append({"address": c["address"], "equity": round(eq, 2),
                            "registry_hits": c["hits"],
                            "last_seen": c["last_seen"]})
                break
        if len(out) >= limit:
            break
    return out
