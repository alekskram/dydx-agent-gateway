"""B3: analytics — dedup window format, prune arithmetic, leaderboard
sorts, usage counters. Written to PROVE two suspected bugs, which are then
fixed in analytics.py (regression protection)."""
from dydx_mcp import analytics


def _count(subject=None):
    with analytics.con() as c:
        if subject:
            return c.execute("SELECT COUNT(*) FROM events WHERE subject=?",
                             (subject,)).fetchone()[0]
        return c.execute("SELECT COUNT(*) FROM events").fetchone()[0]


def test_add_event_dedup_within_2h():
    analytics.add_event("t", "S1", {"v": 1})
    analytics.add_event("t", "S1", {"v": 2})  # duplicate inside window
    assert _count("S1") == 1


def test_add_event_dedup_expires_after_2h_same_day():
    """REGRESSION (bug): legacy ISO-'T'+tz timestamps never compared
    correctly against sqlite datetime('now') — same-day dedup never
    expired. Fixed by julianday() comparison; test uses the legacy format
    exactly as production rows were written before the fix."""
    analytics.add_event("t", "S2", {"v": 1})
    with analytics.con() as c:
        from datetime import datetime, timedelta, timezone
        old = (datetime.now(timezone.utc)
               - timedelta(hours=3)).isoformat(timespec="seconds")
        c.execute("UPDATE events SET ts = ? WHERE subject='S2'", (old,))
    analytics.add_event("t", "S2", {"v": 2})  # window expired -> must add
    assert _count("S2") == 2


def test_add_event_dedup_expires_across_midnight():
    analytics.add_event("t", "S3", {"v": 1})
    with analytics.con() as c:
        c.execute("UPDATE events SET ts = datetime('now','-1 day') "
                  "WHERE subject='S3'")
    analytics.add_event("t", "S3", {"v": 2})
    assert _count("S3") == 2


def test_prune_keeps_exactly_n_with_sparse_ids():
    """REGRESSION (bug): id<=MAX(keep) arithmetic over-deletes when ids
    have gaps; must keep newest N rows regardless of id density."""
    with analytics.con() as c:
        c.execute("DELETE FROM events")
        for i in range(1, 11):
            c.execute("INSERT INTO events(ts,kind,subject,payload) "
                      "VALUES(datetime('now'),'t','P','{}')")
        c.execute("DELETE FROM events WHERE id BETWEEN 5 AND 9")  # gaps
    analytics.prune_events(keep=3)
    assert _count() == 3
    with analytics.con() as c:
        kept = [r["id"] for r in c.execute(
            "SELECT id FROM events ORDER BY id DESC").fetchall()]
    assert kept[0] == 10  # newest kept


def test_leaderboard_metric_sorts():
    with analytics.con() as c:
        c.execute("DELETE FROM leaderboard_runs")
        c.execute("DELETE FROM leaderboard_rows")
        c.execute("INSERT INTO leaderboard_runs VALUES(1,'t',10,3)")
        rows = [("A" * 40, 100.0, 5.0, -50.0, 40.0, 10.0, 50.0, 100.0, 0, 0.1),
                ("B" * 40, 900.0, -5.0, 900.0, 30.0, 20.0, 60.0, 90.0, 0, 0.0),
                ("C" * 40, 10.0, 7.0, 20.0, 60.0, 5.0, 70.0, 80.0, 0, 0.0)]
        for r in rows:
            c.execute("INSERT INTO leaderboard_rows VALUES(1,?,?,?,?,?,?,?,?,?,?)", r)
    lb = analytics.leaderboard(limit=3, metric="pnl_window")
    assert [t["address"][0] for t in lb["top"]] == ["B", "C", "A"]
    lb2 = analytics.leaderboard(limit=2, metric="equity")
    assert [t["address"][0] for t in lb2["top"]] == ["B", "A"]


def test_usage_counters():
    analytics.log_usage("x")
    analytics.log_usage("x")
    analytics.log_usage("y")
    u = analytics.usage_stats()
    assert u["calls_total"] >= 3
    top = dict(u["top_tools"])
    assert top.get("x") == 2
