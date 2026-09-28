"""Runtime configuration.

Secrets are never stored here.  `model_config()` resolves the API key from the
environment at call time and returns only the *name* of the variable to callers
that merely need to describe the configuration, so a key cannot leak into a
response, a log line or the export snapshot.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = BASE_DIR / "VERSION"
try:
    APP_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip() or "0.2.0"
except OSError:
    APP_VERSION = "0.2.0"
DATA_DIR = Path(os.getenv("INTEL_DATA_DIR") or (BASE_DIR / "data"))
SNAPSHOT_DIR = DATA_DIR / "snapshots"
DB_PATH = DATA_DIR / "intel.sqlite"
STATIC_DIR = Path(__file__).resolve().parent / "static"
ENV_FILE = BASE_DIR / ".env"

# The only environment variable names this project understands.
API_KEY_ENV = "DEEPSEEK_API_KEY"
GITHUB_TOKEN_ENV = "GITHUB_TOKEN"

DEFAULT_MODEL_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL_NAME = "deepseek-chat"

_VALID_NAME = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def load_env_file(path: Path | None = None) -> None:
    """Load a minimal KEY=VALUE .env file without mutating already-set variables.

    Deliberately dependency-free: the project ships with a five-package
    requirements file and this format is trivial to parse.
    """
    target = path or ENV_FILE
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError:
        return
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        if name.startswith("export "):
            name = name[len("export "):].strip()
        if not name or not set(name) <= _VALID_NAME or name[0].isdigit():
            continue
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(name, value)


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().casefold() not in {"0", "false", "no", "off", "disabled"}


def model_enabled() -> bool:
    """Whether model-assisted selection should be attempted.

    Off unless a key is actually available, so the system never advertises a
    model path it cannot run.
    """
    if not os.getenv(API_KEY_ENV, "").strip():
        return False
    return _flag("INTEL_USE_MODEL", True)


def model_config() -> dict:
    """Model configuration handed to the intelligence engine.

    `api_key_env` is a variable *name*; the engine resolves the value itself.
    Returns an empty dict when no model is available, which keeps the engine in
    local evidence-extraction mode.
    """
    if not model_enabled():
        return {}
    return {
        "planner": True,
        "base_url": os.getenv("INTEL_MODEL_BASE_URL", "").strip() or DEFAULT_MODEL_BASE_URL,
        "model": os.getenv("INTEL_MODEL_NAME", "").strip() or DEFAULT_MODEL_NAME,
        "api_key_env": API_KEY_ENV,
        "timeout": float(os.getenv("INTEL_MODEL_TIMEOUT", "8") or 8),
    }


def mode_label() -> str:
    """Human-readable processing mode, used by the UI and the health endpoint."""
    return "model_assisted" if model_enabled() else "local_evidence_extraction"


def model_configured() -> bool:
    """True when a key is present and model use is switched on."""
    return model_enabled()


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


load_env_file()
