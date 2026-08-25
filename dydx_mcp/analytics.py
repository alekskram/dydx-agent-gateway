"""Analytics store: leaderboard runs, equity snapshots, event bus."""
import json
import sqlite3
from datetime import datetime, timezone

from .paths import data_dir

DB = data_dir() / "analytics.sqlite"


def con() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS leaderboard_runs(
      id INTEGER PRIMARY KEY, computed_at TEXT,
      accounts_checked INT, accounts_funded INT);
    CREATE TABLE IF NOT EXISTS leaderboard_rows(
      run_id INT, address TEXT, equity REAL, pnl_total REAL, pnl_window REAL,
      day_winrate REAL, max_dd REAL, maker_share REAL, avg_fill REAL,
      farmer_flag INT, identity_residual REAL);
    CREATE TABLE IF NOT EXISTS equity_snapshots(
      address TEXT, ts TEXT, equity REAL);
    CREATE TABLE IF NOT EXISTS events(
      id INTEGER PRIMARY KEY, ts TEXT, kind TEXT, subject TEXT,
      payload TEXT, published INT DEFAULT 0);
    CREATE TABLE IF NOT EXISTS usage(
      ts TEXT DEFAULT (datetime('now')), tool TEXT);
    """)
    return c


def log_usage(tool: str):
    try:
        with con() as c:
            c.execute("INSERT INTO usage(tool) VALUES(?)", (tool,))
    except Exception:  # noqa: BLE001 - metrics must never break serving
        pass


def usage_stats() -> dict:
    """Tool-call counters (traction metrics for the grant KPIs)."""
    with con() as c:
        total = c.execute("SELECT COUNT(*) FROM usage").fetchone()[0]
        last24 = c.execute("SELECT COUNT(*) FROM usage WHERE ts > datetime('now','-1 day')").fetchone()[0]
        last7 = c.execute("SELECT COUNT(*) FROM usage WHERE ts > datetime('now','-7 days')").fetchone()[0]
        top = c.execute("SELECT tool, COUNT(*) n FROM usage GROUP BY tool ORDER BY n DESC LIMIT 5").fetchall()
    return {"calls_total": total, "calls_24h": last24, "calls_7d": last7,
            "top_tools": [(r["tool"], r["n"]) for r in top]}


def add_event(kind: str, subject: str, payload: dict, c: sqlite3.Connection | None = None):
    own = c is None
    c = c or con()
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # dedup: same kind+subject within 2h -> skip
    dup = c.execute(
        "SELECT 1 FROM events WHERE kind=? AND subject=? AND ts > datetime('now','-2 hours')",
        (kind, subject)).fetchone()
    if not dup:
        c.execute("INSERT INTO events(ts,kind,subject,payload) VALUES(?,?,?,?)",
                  (ts, kind, subject, json.dumps(payload)))
        if own:
            c.commit()
    if own:
        c.close()


def prune_events(keep: int = 5000) -> int:
    """Retention: keep only the newest `keep` events (queue hygiene)."""
    with con() as c:
        n = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        if n > keep:
            c.execute("DELETE FROM events WHERE id <= (SELECT MAX(id) FROM events) - ?",
                      (keep,))
        return n - keep if n > keep else 0


def latest_events(limit: int = 20, kind: str | None = None) -> list[dict]:
    with con() as c:
        if kind:
            rows = c.execute("SELECT * FROM events WHERE kind=? ORDER BY id DESC LIMIT ?",
                             (kind, limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?",
                             (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload"])
        out.append(d)
    return out


def leaderboard(limit: int = 20, metric: str = "pnl_window") -> dict:
    with con() as c:
        run = c.execute("SELECT * FROM leaderboard_runs ORDER BY id DESC LIMIT 1").fetchone()
        if not run:
            return {"error": "no leaderboard run yet — run leaderboard.py first"}
        rows = c.execute("SELECT * FROM leaderboard_rows WHERE run_id=?",
                         (run["id"],)).fetchall()
    key = {"pnl_window": "pnl_window", "pnl_total": "pnl_total",
           "equity": "equity", "day_winrate": "day_winrate"}[metric]
    rows = sorted(rows, key=lambda r: -(r[key] or 0))[:limit]
    return {
        "run": dict(run),
        "metric": metric,
        "top": [{**dict(r), "farmer_flag": bool(r["farmer_flag"])} for r in rows],
        "summary": (f"top by {metric}: " + ", ".join(
            f"{r['address'][:10]}… ${r[key]:,.0f}" for r in rows[:5])),
    }
