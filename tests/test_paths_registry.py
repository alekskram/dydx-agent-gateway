"""B7: paths (three data_dir branches) + registry graceful degradation."""
import importlib.util
import sys
from pathlib import Path

import pytest

from dydx_mcp import paths, registry


def test_data_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("DYDX_GATEWAY_DATA", str(tmp_path))
    assert paths.data_dir() == tmp_path


def test_data_dir_repo_branch():
    # running from the repo checkout: ./data next to the package
    d = paths.data_dir.__wrapped__ if hasattr(paths.data_dir, "__wrapped__") \
        else paths.data_dir
    # (env is set by conftest; temporarily clear to check repo default)
    import os
    old = os.environ.pop("DYDX_GATEWAY_DATA", None)
    try:
        assert paths.data_dir() == Path(__file__).parent.parent / "data"
    finally:
        if old:
            os.environ["DYDX_GATEWAY_DATA"] = old


def test_data_dir_installed_branch(monkeypatch, tmp_path):
    # simulate an installed copy: no scanner.py next to the package parent
    pkg = tmp_path / "site-packages" / "dydx_mcp"
    pkg.mkdir(parents=True)
    (pkg / "paths.py").write_text(
        Path(paths.__file__).read_text(), encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("DYDX_GATEWAY_DATA", raising=False)
    spec = importlib.util.spec_from_file_location("installed_paths",
                                                  pkg / "paths.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.data_dir() == home / ".local" / "state" / "dydx-agent-gateway"


def test_registry_graceful_without_db(monkeypatch, tmp_path):
    monkeypatch.setattr(registry, "DB", tmp_path / "missing.sqlite")
    st = registry.stats()
    assert "not built on this host" in st.get("note", "")
    assert registry.recent(5) == []
