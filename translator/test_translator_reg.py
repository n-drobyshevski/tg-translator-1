import pytest
import pytest_asyncio
import asyncio
import logging
import warnings
import types

from translator_reg import (
    run_with_retries,
    entities_to_html,
    format_channel_id,
    validate_channel,
    build_prompt,
)

# Suppress DeprecationWarning from pyrogram.sync about get_event_loop
warnings.filterwarnings(
    "ignore",
    message="There is no current event loop",
    category=DeprecationWarning,
    module="pyrogram.sync"
)

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_run_with_retries_success():
    logger.info("Test run_with_retries: success scenario")
    async def always_succeeds():
        return "Success"
    result = await run_with_retries(always_succeeds)
    assert result == "Success"

@pytest.mark.asyncio
async def test_run_with_retries_failure():
    logger.info("Test run_with_retries: failure scenario")
    async def always_fails():
        raise ValueError("Failure")
    with pytest.raises(ValueError):
        await run_with_retries(always_fails, attempts=2, delay=0)

@pytest.mark.asyncio
async def test_run_with_retries_recovery():
    logger.info("Test run_with_retries: recovery scenario")
    calls = []

    async def fails_once_then_ok():
        if len(calls) == 0:
            calls.append("fail")
            raise RuntimeError("Temporary")
        return "Recovered"

    result = await run_with_retries(fails_once_then_ok, attempts=3, delay=0)
    assert result == "Recovered"
    assert len(calls) == 1

def test_entities_to_html_no_entities():
    logger.info("Test entities_to_html: no_entities")
    text = "Hello world"
    result = entities_to_html(text, None)
    assert result == "Hello world"

def test_entities_to_html_bold():
    logger.info("Test entities_to_html: bold")
    text = "Bold text"
    class FakeEntity:
        offset = 0
        length = 4
        type = "bold"
    result = entities_to_html(text, [FakeEntity()])
    logger.info("entities_to_html (bold) result: %r", result)
    assert "<b>Bold</b>" in result

def test_entities_to_html_text_link():
    logger.info("Test entities_to_html: text_link")
    text = "Click here"
    class FakeEntity:
        offset = 0
        length = 5
        type = "text_link"
        url = "https://example.com"
    result = entities_to_html(text, [FakeEntity()])
    logger.info("entities_to_html (text_link) result: %r", result)
    assert '<a href="https://example.com">Click</a>' in result

def test_entities_to_html_text_mention():
    logger.info("Test entities_to_html: text_mention")
    text = "User"
    class FakeUser:
        id = 12345
    class FakeEntity:
        offset = 0
        length = 4
        type = "text_mention"
        user = FakeUser()
    result = entities_to_html(text, [FakeEntity()])
    logger.info("entities_to_html (text_mention) result: %r", result)
    assert 'href="tg://user?id=12345"' in result

def test_entities_to_html_code_and_pre():
    logger.info("Test entities_to_html: code and pre")
    text = "code block"
    class FakeEntityCode:
        offset = 0
        length = 4
        type = "code"
    class FakeEntityPre:
        offset = 5
        length = 5
        type = "pre"
        language = "python"
    result = entities_to_html(text, [FakeEntityCode(), FakeEntityPre()])
    logger.info("entities_to_html (code and pre) result: %r", result)
    assert "<code>" in result or "<pre><code" in result

def test_load_config_env(monkeypatch):
    logger.info("Test load_config: env present")
    from translator_reg import load_config
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    monkeypatch.setenv("CHRISTIANVISION_CHANNEL", "1")
    monkeypatch.setenv("SHALTNOTKILL_CHANNEL", "2")
    monkeypatch.setenv("SOURCE_TEST_ID", "3")
    config = load_config()
    assert config["BOT_TOKEN"] == "token"
    assert config["ANTHROPIC_API_KEY"] == "key"

def test_get_channel_mapping():
    logger.info("Test get_channel_mapping")
    from translator_reg import get_channel_mapping
    env = {
        "CHRISTIANVISION_CHANNEL": "1",
        "SHALTNOTKILL_CHANNEL": "2",
        "SOURCE_TEST_ID": "3"
    }
    mapping = get_channel_mapping(env)
    assert mapping[1] == "christianvision"
    assert mapping[2] == "shaltnotkill"
    assert mapping[3] == "test"

def test_build_prompt_includes_html():
    logger.info("Test build_prompt: includes html")
    html = "<b>hello</b>"
    prompt = build_prompt(html, "chan", "link")
    assert html in prompt

def test_metadata_request_repr():
    logger.info("Test MetadataRequest: __repr__")
    from translator_reg import MetadataRequest
    req = MetadataRequest(1, 2, "fileid")
    s = repr(req)
    assert "MetaReq" in s and "fileid" in s

def test_format_channel_id_variants():
    logger.info("Test format_channel_id: variants")
    assert format_channel_id("@mychannel") == "@mychannel"
    assert format_channel_id("-1001234567890") == "-1001234567890"
    assert format_channel_id("1234567890") == "-1001234567890"
    assert format_channel_id("my_channel") == "@my_channel"
    assert format_channel_id("") is None
    assert format_channel_id(None) is None

def test_build_prompt_short():
    logger.info("Test build_prompt: short message")
    html = "Short msg"
    prompt = build_prompt(html, "chan", "link")
    assert "Translate the following HTML message" in prompt
    assert html in prompt

def test_build_prompt_long():
    logger.info("Test build_prompt: long message")
    html = "This is a long message with more than seven words for testing the prompt template."
    prompt = build_prompt(html, "chan", "link")
    assert "Translate the following HTML message" not in prompt
    assert html in prompt

def test_validate_channel_success(monkeypatch):
    logger.info("Test validate_channel: success")
    class FakeResponse:
        status_code = 200
        def json(self):
            return {"result": {"title": "Test", "type": "channel"}}
    def fake_get(*a, **k):
        return FakeResponse()
    monkeypatch.setattr("requests.get", fake_get)
    # Should not raise
    validate_channel("-1001234567890", "test", "token")

def test_validate_channel_failure(monkeypatch):
    logger.info("Test validate_channel: failure")
    class FakeResponse:
        status_code = 400
        def json(self):
            return {"description": "Not found"}
    def fake_get(*a, **k):
        return FakeResponse()
    monkeypatch.setattr("requests.get", fake_get)
    import pytest
    with pytest.raises(ValueError):
        validate_channel("-1001234567890", "test", "token")

def test_register_handlers_no_send(monkeypatch):
    logger.info("Test register_handlers: no actual send")

    # Fake Pyrogram Client
    class FakeClient:
        def __init__(self):
            self.handlers = []
        def on_message(self, filt):
            def decorator(fn):
                self.handlers.append(fn)
                return fn
            return decorator

    # Fake Anthropic
    class FakeAnthropic:
        pass

    # Fake TelegramSender
    class FakeSender:
        async def send_message(self, *a, **k):
            logger.info("FakeSender.send_message called with: %r %r", a, k)

    # Fake mapping
    mapping = {123: "target"}

    # Patch translate_html to avoid real API call
    async def fake_translate_html(client, payload):
        logger.info("fake_translate_html called with: %r", payload)
        return "translated"

    monkeypatch.setattr("translator_reg.translate_html", fake_translate_html)

    pyro = FakeClient()
    anthropic = FakeAnthropic()
    sender = FakeSender()

    from translator_reg import register_handlers
    register_handlers(pyro, anthropic, sender, mapping)
    assert pyro.handlers, "Handler should be registered"

    # Simulate a message
    class FakeMsg:
        id = 1
        chat = type("Chat", (), {"id": 123, "username": "chan", "title": "Chan"})()
        text = "hi"
        caption = None
        document = None
        photo = None
        video = None
        entities = None
        caption_entities = None

    # Run the handler in a fresh event loop to avoid blocking the main pytest loop
    import threading

    result_holder = {}

    def run_handler():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result_holder["result"] = loop.run_until_complete(pyro.handlers[0](pyro, FakeMsg()))
        finally:
            loop.close()

    t = threading.Thread(target=run_handler)
    t.start()
    t.join(timeout=5)
    assert not t.is_alive(), "Handler thread should finish and not block"

def test_ptb_worker_no_send(monkeypatch):
    logger.info("Test ptb_worker: no actual send")
    from translator_reg import ptb_worker, MetadataRequest

    class FakeBot:
        async def get_chat(self, chat_id):
            return type("Chat", (), {"to_dict": lambda self: {"id": chat_id}, "username": "chan", "title": "Chan"})()
        async def get_file(self, file_id):
            return type("File", (), {"to_dict": lambda self: {"file_id": file_id}, "file_path": "path"})()
        token = "token"

    class FakeApp:
        bot = FakeBot()

    stop_event = asyncio.Event()

    # Prepare a MetadataRequest and put it in the queue
    req = MetadataRequest(123, 1, "fileid")
    # Set up a short queue for the worker
    from translator_reg import query_queue
    async def put_req():
        await query_queue.put(req)
        # Stop after one iteration
        stop_event.set()
    asyncio.run(put_req())

    # Should not raise
    asyncio.run(ptb_worker(FakeApp(), stop_event))
    assert req.response.done()
    meta = req.response.result()
    logger.info("ptb_worker meta result: %r", meta)
