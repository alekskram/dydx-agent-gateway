"""Data directory resolution for pip-installed vs repo copies.

- Repo checkout (scanner.py next to the package): use ./data as before.
- Installed package: keep state OUT of site-packages ->
  ~/.local/state/dydx-agent-gateway (overridable via DYDX_GATEWAY_DATA).
"""
import os
from pathlib import Path


def data_dir() -> Path:
    env = os.environ.get("DYDX_GATEWAY_DATA")
    if env:
        d = Path(env)
    elif (Path(__file__).parent.parent / "scanner.py").exists():
        d = Path(__file__).parent.parent / "data"  # running from repo
    else:
        d = Path.home() / ".local" / "state" / "dydx-agent-gateway"
    d.mkdir(parents=True, exist_ok=True)
    return d
