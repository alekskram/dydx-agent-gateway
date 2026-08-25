"""Test isolation: redirect ALL data to a per-session temp dir BEFORE any
dydx_mcp import (analytics/registry resolve DB paths at import time).
Production data/ is never touched by the test suite."""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="dydx-qa-")
os.environ["DYDX_GATEWAY_DATA"] = _TMP
