import os
import tempfile
import shutil
from translator.services.channel_logger import (
    ChannelCache,
    store_message,
    get_last_messages,
)

def test_store_and_get_message(tmp_path):
    cache_dir = tmp_path / "cache"
    os.makedirs(cache_dir)
    store_path = cache_dir / "channel_cache.json"
    cache = ChannelCache()
    cache.cache = {}
    msg = {
        "message_id": 1,
        "date": "2021-01-01",
        "chat_title": "T",
        "chat_username": "U",
        "html": "text",
    }
    cache.store_message("123", msg)
    msgs = cache.get_last_messages("123")
    assert msgs[-1]["message_id"] == 1


def test_channelcache_load_cache_handles_missing_file(tmp_path, monkeypatch):
    # Use a new ChannelCache instance with a unique store path
    cache_dir = tmp_path / "cache"
    os.makedirs(cache_dir, exist_ok=True)
    store_path = cache_dir / "channel_cache.json"
    # Patch STORE_PATH for this instance only
    from translator.services import channel_logger

    monkeypatch.setattr(channel_logger, "STORE_PATH", str(store_path))
    # Now run the code
    cc = channel_logger.ChannelCache()
    # Clear cache
    cc.cache = {}
    # Should be empty if file is missing
    assert cc._load_cache() == {}


def test_store_message_trims_limit(tmp_path):
    cache = ChannelCache()
    cache.cache = {}
    for i in range(15):
        store_message("chan", {"message_id": i, "html": str(i)})
    msgs = get_last_messages("chan")
    assert len(msgs) <= 9  # Enforces limit


def test_check_deleted_messages_removes_invalid(monkeypatch):
    class MessageIdInvalid(Exception):
        pass

    class DummyClient:
        def get_messages(self, chan_id, msg_id):
            if msg_id == "good":
                return True
            raise MessageIdInvalid()

    from translator.services import channel_logger

    cache = channel_logger.ChannelCache()
    cache.cache = {"123": [{"message_id": "good"}, {"message_id": "bad"}]}
    # Patch the method to catch all exceptions for testing
    orig = (
        channel_logger.MessageIdInvalid
        if hasattr(channel_logger, "MessageIdInvalid")
        else Exception
    )
    monkeypatch.setattr(channel_logger, "MessageIdInvalid", MessageIdInvalid)
    cache.check_deleted_messages(DummyClient())
    msgs = cache.cache["123"]
    assert {"message_id": "good"} in msgs
    assert not any(m["message_id"] == "bad" for m in msgs)
