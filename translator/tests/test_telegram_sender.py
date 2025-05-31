import pytest
from unittest.mock import patch, MagicMock
from translator.services.telegram_sender import TelegramSender


def test_split_message_short():
    sender = TelegramSender()
    text = "short text"
    assert sender.split_message(text) == [text]


def test_split_message_long():
    sender = TelegramSender()
    long_line = "A" * (sender.MAX_MESSAGE_LENGTH + 5)
    messages = sender.split_message(long_line)
    assert len(messages) == 2
    assert "".join(messages).replace("\n", "") == long_line


@pytest.mark.asyncio
@patch("requests.Session.post")
async def test_send_message_unknown_channel(mock_post):
    sender = TelegramSender()
    ok, chat_id = await sender.send_message("text", "notachannel", {})
    assert not ok
    assert chat_id is None


@pytest.mark.asyncio
@patch("requests.Session.post")
async def test_send_message_no_channel_id(mock_post):
    sender = TelegramSender()
    # Temporarily mess up a config entry
    orig = sender.configs["test"].channel_id
    sender.configs["test"].channel_id = None
    ok, chat_id = await sender.send_message("text", "test", {})
    sender.configs["test"].channel_id = orig
    assert not ok
    assert chat_id is None


@pytest.mark.asyncio
@patch("requests.Session.post")
async def test_send_message_api_error(mock_post):
    mock_post.return_value.status_code = 400
    mock_post.return_value.json.return_value = {"description": "fail"}
    sender = TelegramSender()
    sender.configs["test"].channel_id = 123
    ok, chat_id = await sender.send_message("text", "test", {})
    assert not ok


@pytest.mark.asyncio
@patch("requests.Session.post")
async def test_send_message_success(mock_post):
    # Simulate success response
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "result": {"message_id": 1, "chat": {"id": 123}},
        "ok": True,
    }
    sender = TelegramSender()
    sender.configs["test"].channel_id = 123
    ok, chat_id = await sender.send_message("test", "test", {})
    assert ok
    assert chat_id == 123


@pytest.mark.asyncio
@patch("requests.Session.post")
async def test_send_message_exception(mock_post):
    mock_post.side_effect = Exception("fail!")
    sender = TelegramSender()
    sender.configs["test"].channel_id = 123
    ok, chat_id = await sender.send_message("hi", "test", {})
    assert not ok
    assert chat_id is None
