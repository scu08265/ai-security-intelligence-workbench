"""运行配置的解析顺序：显式环境变量 > .env > 默认路径。

回归背景：`app/config.py` 曾在**计算完** `DATA_DIR` / `APP_VERSION` 之后才调用
`load_env_file()`，于是 `.env` 里的 `INTEL_DATA_DIR` 被静默忽略，只有显式环境变量
生效；命令行工具也因此各自写死机器路径。这里把三层优先级固定下来。

测试只用临时目录，不接触真实数据目录，也不发起任何网络请求。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app import config

ROOT = Path(__file__).resolve().parents[1]


def _run(code: str, *, env_file: Path | None, data_dir: str | None) -> str:
    env = {k: v for k, v in os.environ.items() if k != "INTEL_DATA_DIR"}
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    if env_file is not None:
        env["INTEL_ENV_FILE"] = str(env_file)
    else:
        env.pop("INTEL_ENV_FILE", None)
    if data_dir is not None:
        env["INTEL_DATA_DIR"] = data_dir
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def test_resolve_data_dir_defaults_to_the_repo_data_folder():
    assert config.resolve_data_dir({}) == config.BASE_DIR / "data"
    assert config.resolve_data_dir({"INTEL_DATA_DIR": "   "}) == config.BASE_DIR / "data"


def test_resolve_data_dir_prefers_an_explicit_value():
    assert config.resolve_data_dir({"INTEL_DATA_DIR": r"D:\explicit"}) == Path(r"D:\explicit")


def test_load_env_file_fills_missing_names_only(tmp_path):
    env_file = tmp_path / "env"
    env_file.write_text(
        "# comment\n"
        "\n"
        "INTEL_DATA_DIR=/from/env/file\n"
        "export EXPORTED_NAME=exported\n"
        "1INVALID=x\n"
        "NOT A NAME=x\n"
        'QUOTED="quoted value"\n',
        encoding="utf-8",
    )
    os.environ.pop("INTEL_DATA_DIR", None)
    for name in ("EXPORTED_NAME", "QUOTED"):
        os.environ.pop(name, None)
    try:
        config.load_env_file(env_file)
        assert os.environ["INTEL_DATA_DIR"] == "/from/env/file"
        assert os.environ["EXPORTED_NAME"] == "exported"
        assert os.environ["QUOTED"] == "quoted value"
        assert "1INVALID" not in os.environ
        assert "NOT A NAME" not in os.environ
    finally:
        for name in ("INTEL_DATA_DIR", "EXPORTED_NAME", "QUOTED"):
            os.environ.pop(name, None)


def test_load_env_file_never_overrides_an_explicit_variable(monkeypatch, tmp_path):
    env_file = tmp_path / "env"
    env_file.write_text("INTEL_DATA_DIR=/from/env/file\n", encoding="utf-8")
    monkeypatch.setenv("INTEL_DATA_DIR", "/explicit")
    config.load_env_file(env_file)
    assert os.environ["INTEL_DATA_DIR"] == "/explicit"
    assert config.resolve_data_dir() == Path("/explicit")


def test_data_dir_uses_the_env_file_when_no_variable_is_set(tmp_path):
    env_file = tmp_path / "env"
    target = tmp_path / "corpus"
    env_file.write_text(f"INTEL_DATA_DIR={target}\n", encoding="utf-8")
    out = _run("import app.config as c; print(c.DATA_DIR)", env_file=env_file,
               data_dir=None)
    assert Path(out) == target
    # load_env_file 必须在计算 DATA_DIR 之前跑，否则这里会打印出 BASE_DIR/data


def test_explicit_variable_still_beats_the_env_file(tmp_path):
    env_file = tmp_path / "env"
    env_file.write_text("INTEL_DATA_DIR=/from/env/file\n", encoding="utf-8")
    out = _run("import app.config as c; print(c.DATA_DIR)", env_file=env_file,
               data_dir="/explicit")
    assert Path(out) == Path("/explicit")


def test_data_dir_falls_back_to_the_repo_default(tmp_path):
    out = _run("import app.config as c; print(c.DATA_DIR)", env_file=None, data_dir=None)
    assert Path(out) == config.BASE_DIR / "data"


def test_cli_tools_reuse_the_app_config_init(tmp_path):
    """命令行工具的默认库目录来自配置解析，而不是写死的机器路径。"""
    env_file = tmp_path / "env"
    target = tmp_path / "corpus"
    env_file.write_text(f"INTEL_DATA_DIR={target}\n", encoding="utf-8")
    code = (
        "import sys; sys.path.insert(0, 'tools');"
        "import build_b_relation_gold as g;"
        "import verify_b_relation_expansion as v;"
        "print(g.DEFAULT_DB_DIR);"
        "print(v.build_parser().get_default('db_dir'))"
    )
    out = _run(code, env_file=env_file, data_dir=None).splitlines()
    assert Path(out[0]) == target
    assert Path(out[1]) == target
