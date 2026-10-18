"""模型密钥变量名可切换，便于换供应商而不用改名。"""

from __future__ import annotations

from app import config, model_chain


def test_default_key_variable_stays_deepseek(monkeypatch):
    monkeypatch.delenv(config.API_KEY_ENV_OVERRIDE, raising=False)
    assert config.model_api_key_env() == "DEEPSEEK_API_KEY"


def test_override_lets_another_provider_keep_its_own_variable(monkeypatch):
    monkeypatch.setenv(config.API_KEY_ENV_OVERRIDE, "OPENAI_API_KEY")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-only")
    monkeypatch.setenv("INTEL_USE_MODEL", "1")

    assert config.model_api_key_env() == "OPENAI_API_KEY"
    assert config.model_enabled() is True
    assert config.model_config()["api_key_env"] == "OPENAI_API_KEY"
    assert model_chain.chain()["active_level"] == 1


def test_override_without_a_key_keeps_the_system_local(monkeypatch):
    monkeypatch.setenv(config.API_KEY_ENV_OVERRIDE, "OPENAI_API_KEY")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-should-be-ignored")

    assert config.model_enabled() is False
    assert model_chain.chain()["active_level"] == 3
