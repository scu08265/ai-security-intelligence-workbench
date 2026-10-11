"""Runtime configuration.

Secrets are never stored here.  `model_config()` resolves the API key from the
environment at call time and returns only the *name* of the variable to callers
that merely need to describe the configuration, so a key cannot leak into a
response, a log line or the export snapshot.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = BASE_DIR / "VERSION"

# ``INTEL_ENV_FILE`` only redirects where the .env is read from (useful for tests and
# for pointing a checkout at a shared .env); it never changes precedence.
ENV_FILE = Path(os.getenv("INTEL_ENV_FILE") or (BASE_DIR / ".env"))

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


# 必须在任何 os.getenv 读取配置之前执行：否则 .env 里的 INTEL_DATA_DIR / APP_VERSION
# 会被"先算好的模块常量"绕过，只有显式环境变量生效。
# os.environ.setdefault 保证显式环境变量 > .env > 默认值 的优先级不变。
load_env_file()

try:
    _FILE_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()
except OSError:
    _FILE_VERSION = ""
APP_VERSION = (
    os.getenv("APP_VERSION", "").strip()
    or _FILE_VERSION
    or "0.2.3"
)


def resolve_data_dir(source: Mapping[str, str] | None = None) -> Path:
    """数据集目录：显式 ``INTEL_DATA_DIR`` > 默认 ``BASE_DIR/data``。

    ``.env`` 里的值由 :func:`load_env_file` 写进 ``os.environ``（``setdefault``），
    所以它同样生效，但不会覆盖已经显式设置的环境变量。
    """
    values = os.environ if source is None else source
    raw = (values.get("INTEL_DATA_DIR") or "").strip()
    return Path(raw) if raw else (BASE_DIR / "data")


DATA_DIR = resolve_data_dir()
SNAPSHOT_DIR = DATA_DIR / "snapshots"
DB_PATH = DATA_DIR / "intel.sqlite"
STATIC_DIR = Path(__file__).resolve().parent / "static"


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
