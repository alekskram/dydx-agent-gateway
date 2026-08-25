"""B5: scanner — bech32 validation table, block parsing, scan idempotency."""
import base64
import sqlite3

import scanner


GOOD = "dydx1m9hg73dtn5ku8ulmj8rjmdqh0hk7uuhawc69cn"


def test_valid_table():
    assert scanner.valid(GOOD)
    assert not scanner.valid(GOOD[:-1])                      # truncated
    assert not scanner.valid(GOOD[:-1] + ("q" if GOOD[-1] != "q" else "p"))
    assert not scanner.valid("dydx1" + "q" * 37)             # wrong length
    assert not scanner.valid("1" + GOOD[1:])                 # wrong hrp


def test_block_addresses_extracts_from_tx_bytes(monkeypatch):
    raw = GOOD.encode()
    other = ("dydx1" + "b" * 38).encode()
    frag = b"dydx1shortfragment"  # below regex length -> ignored by regex
    txs = [base64.b64encode(raw + b"\x02\x00" + other).decode(),
           base64.b64encode(frag).decode()]

    def fake_rpc(method, params, timeout=20):
        return {"result": {"block": {"data": {"txs": txs}}}}

    monkeypatch.setattr(scanner, "rpc", fake_rpc)
    got = scanner.block_addresses(123)
    assert got == {GOOD, "dydx1" + "b" * 38}


def test_scan_idempotent_no_double_hits(monkeypatch, tmp_path):
    """The same block scanned twice (crash-restart scenario) must not
    double-count hits — UNIQUE(address, height) guard."""
    db = tmp_path / "registry.sqlite"
    monkeypatch.setattr(scanner, "DB", db)
    monkeypatch.setattr(scanner, "latest_height", lambda: 105)
    monkeypatch.setattr(scanner, "block_addresses",
                        lambda h: {GOOD} if h == 103 else set())
    scanner.run(n_blocks=3)   # heights 103..105 (first run: cursor starts 105-3)
    with sqlite3.connect(db) as con:
        h1 = con.execute("SELECT hits FROM addresses WHERE address=?",
                         (GOOD,)).fetchone()[0]
        blocks = con.execute("SELECT COUNT(*) FROM addr_blocks").fetchone()[0]
    assert h1 == 1 and blocks == 1
    # crash-restart: rescan the same heights (cursor rewound)
    with sqlite3.connect(db) as con:
        con.execute("UPDATE meta SET v='102' WHERE k='cursor'")
        con.commit()
    scanner.run(n_blocks=3)
    with sqlite3.connect(db) as con:
        h2 = con.execute("SELECT hits FROM addresses WHERE address=?",
                         (GOOD,)).fetchone()[0]
        blocks2 = con.execute("SELECT COUNT(*) FROM addr_blocks").fetchone()[0]
    assert h2 == 1 and blocks2 == 1  # no double counting
