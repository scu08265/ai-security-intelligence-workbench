"""Shared test fixtures.

Every test runs against a throwaway data directory and with the model key
removed, so the suite is fully offline and deterministic: no test can reach the
network or spend model budget.
"""

from __future__ import annotations

import os
import tempfile

# Must happen before `app` is imported anywhere, because config resolves its
# paths at import time and app.api creates the database on import.
os.environ.setdefault("INTEL_DATA_DIR", tempfile.mkdtemp(prefix="intel-test-boot-"))

import pytest  # noqa: E402

from app import collectors, config, storage  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Point storage at a per-test directory and force local-only mode."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "SNAPSHOT_DIR", data_dir / "snapshots")
    monkeypatch.setattr(config, "DB_PATH", data_dir / "intel.sqlite")
    # No model calls in tests: they are non-deterministic and cost money.
    monkeypatch.delenv(config.API_KEY_ENV, raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # Retry tests exercise the retry path, not the wall-clock backoff.
    monkeypatch.setattr(collectors, "BACKOFF_SECONDS", (0.0, 0.0, 0.0))
    config.ensure_dirs()
    storage.init_db()
    yield
    collectors.set_transport(None)
