import os
import pytest
from translator.config import Config

def test_config_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "api")
    monkeypatch.setenv("SOURCE_TEST_ID", "1")
    monkeypatch.setenv("CHRISTIANVISION_CHANNEL", "11")
    monkeypatch.setenv("SHALTNOTKILL_CHANNEL", "22")
    cfg = Config()
    cfg.validate()
    d = cfg.as_dict()
    assert d["TELEGRAM_BOT_TOKEN"] == "tok"
    assert "CHANNELS" in d


def set_all_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "api")
    monkeypatch.setenv("SOURCE_TEST_ID", "42")
    monkeypatch.setenv("CHRISTIANVISION_CHANNEL", "10")
    monkeypatch.setenv("SHALTNOTKILL_CHANNEL", "20")


def test_config_reload(monkeypatch):
    set_all_env(monkeypatch)
    cfg = Config()
    cfg.reload()
    assert cfg.TELEGRAM_BOT_TOKEN == "tok"
    assert cfg.TELEGRAM_API_ID == 1
    assert cfg.get_channel_id("test") == 42


def test_config_validate_missing(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "api")
    monkeypatch.setenv("SOURCE_TEST_ID", "42")
    monkeypatch.setenv("CHRISTIANVISION_CHANNEL", "10")
    monkeypatch.setenv("SHALTNOTKILL_CHANNEL", "20")
    with pytest.raises(RuntimeError) as e:
        Config()
    assert "TELEGRAM_BOT_TOKEN" in str(e.value)


def test_config_as_dict(monkeypatch):
    set_all_env(monkeypatch)
    cfg = Config()
    d = cfg.as_dict()
    assert d["TELEGRAM_BOT_TOKEN"] == "tok"
    assert "CHANNELS" in d
    assert "LOG_LEVEL" in d
