import pytest
import asyncio
import types
from translator import bot


def test_import_bot_module():
    # Just import, should not crash
    import translator.bot



def test_init_clients_smoke(monkeypatch):
    # Patch out external dependencies and constructor side effects
    class DummyClient:
        pass

    class DummyAnthropic:
        pass

    class DummySender:
        pass

    class DummyBuilder:
        def token(self, token):
            return self

        def rate_limiter(self, rl):
            return self

        def build(self):
            return DummyClient()

    class DummyApp:
        builder = lambda: DummyBuilder()

    monkeypatch.setattr(bot, "Client", lambda *a, **k: DummyClient())
    monkeypatch.setattr(bot, "Application", DummyApp)
    monkeypatch.setattr(bot, "Anthropic", lambda **k: DummyAnthropic())
    monkeypatch.setattr(bot, "TelegramSender", lambda: DummySender())
    env = {
        "BOT_TOKEN": "tok",
        "ANTHROPIC_API_KEY": "api",
        "CHRISTIANVISION_CHANNEL": "1",
        "SHALTNOTKILL_CHANNEL": "2",
        "SOURCE_TEST_ID": "3",
    }
    pyro, ptb_app, anthropic, sender = bot.init_clients()
    assert (
        pyro is not None
        and ptb_app is not None
        and anthropic is not None
        and sender is not None
    )


def test_register_handlers_runs(monkeypatch):
    # Create dummy dependencies
    class DummyPyro:
        def on_message(self, filt):
            def deco(fn):
                return fn

            return deco

    class DummyAnthropic:
        pass

    class DummySender:
        pass

    mapping = {1: "foo"}
    # Should not crash
    bot.register_handlers(DummyPyro(), DummyAnthropic(), DummySender(), mapping)


@pytest.mark.asyncio
async def test_ptb_worker_empty(monkeypatch):
    class DummyBot:
        async def get_chat(self, chat_id):
            return types.SimpleNamespace(
                to_dict=lambda: {"id": chat_id, "title": "t"}, username="user"
            )

        async def get_file(self, file_id):
            return types.SimpleNamespace(
                to_dict=lambda: {"id": file_id, "file_path": "a/b/c"}
            )

    class DummyApp:
        bot = DummyBot()

    queue = bot.query_queue
    # Clear the queue
    while not queue.empty():
        queue.get_nowait()
    stop_event = asyncio.Event()

    async def stop_soon():
        await asyncio.sleep(0.01)
        stop_event.set()
        # Also put a dummy item so the queue.get() can complete
        queue.put_nowait(
            types.SimpleNamespace(
                chat_id=1,
                message_id=1,
                file_id=None,
                message_entities=[],
                response=asyncio.Future(),
            )
        )

    # Schedule stopping
    asyncio.create_task(stop_soon())
    # Run worker with a timeout to avoid infinite hang
    try:
        await asyncio.wait_for(bot.ptb_worker(DummyApp(), stop_event), timeout=0.2)
    except asyncio.TimeoutError:
        pytest.fail("ptb_worker did not finish in time")


def test_main_async_signature():
    # Ensure main_async is defined and is async
    assert hasattr(bot, "main_async")
    assert callable(bot.main_async)
    assert bot.main_async.__code__.co_flags & 0x80  # CO_COROUTINE
