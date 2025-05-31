from types import SimpleNamespace
import pytest
from translator.utils.message_utils import (
    get_media_info,
    build_payload,
    log_and_store_message,
    extract_channel_info,
)


class DummyMsg(SimpleNamespace):
    pass


def test_get_media_info_none():
    msg = DummyMsg(document=None, photo=None, video=None)
    assert get_media_info(msg, 1) == (None, None, "text")


def test_get_media_info_large_file():
    doc = SimpleNamespace(file_id="id", file_size=5000)
    msg = DummyMsg(document=doc, photo=None, video=None)
    # Too large: should fall back to text
    assert get_media_info(msg, 1) == (None, None, "text")


def test_build_payload_no_username():
    chat = SimpleNamespace(title="T", username=None)
    msg = DummyMsg(chat=chat, id=11, text=None, caption="c")
    res = build_payload(msg, "html", {})
    assert "Source channel: T" in res["Html"]


def test_log_and_store_message_sets_id(monkeypatch):
    data = {}

    def fake_store_message(cid, msgdata):
        data["msg"] = msgdata

    monkeypatch.setattr(
        "translator.utils.message_utils.store_message", fake_store_message
    )
    chat = SimpleNamespace(id=44, title="A", username="B")
    msg = DummyMsg(id=55, chat=chat)
    msg_id = log_and_store_message(msg, "html")
    assert data["msg"]["html"] == "html"
    assert msg_id == 55


def test_extract_channel_info_missing_dst(monkeypatch):
    chat = SimpleNamespace(id=4, title="ZZ")
    msg = DummyMsg(chat=chat)
    mapping = {2: "test"}
    src_id, src_name, dst_id, dst_name = extract_channel_info(msg, mapping, "missing")
    assert dst_id == ""
    assert dst_name == "missing"
    assert src_id == "4"
    assert src_name == "ZZ"


def test_get_media_info_text_only():
    m = DummyMsg(document=None, photo=None, video=None)
    assert get_media_info(m, 10_000) == (None, None, "text")


def test_build_payload_includes_channel_link():
    m = DummyMsg(
        chat=SimpleNamespace(title="T", username="U"), id=1, text="Hi", caption=None
    )
    res = build_payload(m, "<b>Test</b>", {})
    assert "Source channel:" in res["Html"]


def test_extract_channel_info_finds_dst_id():
    m = DummyMsg(chat=SimpleNamespace(id=2, title="n"), entities=None)
    mapping = {2: "dst", 1: "src"}
    src_id, src_name, dst_id, dst_name = extract_channel_info(m, mapping, "dst")
    assert dst_id == "2"  # Should match the string version of 2
    assert dst_name == "dst"
    assert src_id == "2"
    assert src_name == "n"
