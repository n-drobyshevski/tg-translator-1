"""
Bidirectional Pyrogram ⇆ PTB relay bot.

• Pyrogram прослушивает исходные каналы.
• Для каждого сообщения формирует MetadataRequest и кладёт в очередь.
• Фоновый ptb_worker снимает запрос, вытаскивает максимум метаданных через Bot API
  и резолвит future.
• Pyrogram дожидается future, обогащает сообщение и переводит/пересылает.

"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import requests
import signal
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from anthropic import Anthropic
from dotenv import load_dotenv
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.enums import MessageEntityType
from pyrogram.types import MessageEntity
from telegram.error import TelegramError
from telegram.ext import Application

# Optional rate‑limiter (requires PTB extra)
try:
    from telegram.ext import AIORateLimiter  # type: ignore
except ImportError:  # pragma: no cover
    AIORateLimiter = None  # noqa: N816 — keep sentinel upper‑case

# Import TelegramSender with fallback
try:
    from .telegram_sender import TelegramSender  # type: ignore
except ImportError:  # pragma: no cover
    from telegram_sender import TelegramSender  # type: ignore

# Import channel_logger with explicit relative import for package context
try:
    from .channel_logger import register_channel_logger, check_deleted_messages, store_message
except ImportError:
    from channel_logger import register_channel_logger, check_deleted_messages, store_message


###############################################################################
# Logging
###############################################################################
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s — %(levelname)s — %(name)s — %(message)s",
)
logger = logging.getLogger("MAIN")
pyro_log = logging.getLogger("PYRO")
ptb_log = logging.getLogger("PTB")

###############################################################################
# Template
###############################################################################
TEMPLATE_PATH = Path(__file__).parent / "prompt_template.txt"
PROMPT_TEMPLATE = (
    TEMPLATE_PATH.read_text(encoding="utf-8")
    if TEMPLATE_PATH.exists()
    else "{message_text}"
)
###############################################################################
# Helpers: HTML reconstruction
###############################################################################


def entities_to_html(text: str, entities: List[Any] | None) -> str:
    escaped = html.escape(text)
    if not entities:
        return escaped

    entities_sorted = sorted(entities, key=lambda e: e.offset, reverse=True)

    for ent in entities_sorted:
        start, length = ent.offset, ent.length
        end = start + length

        if ent.type == MessageEntityType.BOLD:
            open_tag, close_tag = "<b>", "</b>"
        elif ent.type == MessageEntityType.ITALIC:
            open_tag, close_tag = "<i>", "</i>"
        elif ent.type == MessageEntityType.CODE:
            open_tag, close_tag = "<code>", "</code>"
        elif ent.type == MessageEntityType.PRE:
            # ent.language peut exister
            lang = getattr(ent, "language", "")
            open_tag = f'<pre><code{" language="+html.escape(lang) if lang else ""}>'
            close_tag = "</code></pre>"
        elif ent.type == MessageEntityType.TEXT_LINK:
            url = html.escape(ent.url)
            open_tag = f'<a href="{url}">'
            close_tag = "</a>"
        elif ent.type == MessageEntityType.TEXT_MENTION:
            user_id = ent.user.id
            # on génère un lien vers l’utilisateur
            open_tag = f'<a href="tg://user?id={user_id}">'
            close_tag = "</a>"
        else:
            # Ignorer или добавить другие случаи…
            continue

        # 4. Вставить теги (в экранированную строку)
        #   Разрезаем строку и вставляем
        before = escaped[:start]
        middle = escaped[start:end]
        after = escaped[end:]
        escaped = before + open_tag + middle + close_tag + after
    return escaped


async def run_with_retries(coro, *args, attempts=3, delay=2):
    for i in range(attempts):
        try:
            return await coro(*args)
        except Exception as e:
            pyro_log.warning("Retry attempt %s for %s: %s", i + 1, coro.__name__, e)
            if i == attempts - 1:
                raise
            await asyncio.sleep(delay)


###############################################################################
# Data containers
###############################################################################
class MetadataRequest:
    def __init__(self, chat_id: int, message_id: int, file_id: str | None = None):
        self.chat_id = chat_id
        self.message_id = message_id
        self.file_id = file_id
        # raw entities of the original message (list[dict])
        self.message_entities: List[Dict[str, Any]] | None = None
        self.response: asyncio.Future[Dict[str, Any]] = (
            asyncio.get_event_loop().create_future()
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MetaReq {self.chat_id}/{self.message_id} file_id={self.file_id}>"


# Очередь общения Pyrogram → PTB
query_queue: asyncio.Queue[MetadataRequest] = asyncio.Queue()

###############################################################################
# Конфиг и инициализация клиентов
###############################################################################


def load_config() -> Dict[str, str]:
    load_dotenv()
    required = {
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "CHRISTIANVISION_CHANNEL": os.getenv("CHRISTIANVISION_CHANNEL"),
        "SHALTNOTKILL_CHANNEL": os.getenv("SHALTNOTKILL_CHANNEL"),
        "SOURCE_TEST_ID": os.getenv("SOURCE_TEST_ID"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        logger.error("Missing env vars: %s", ", ".join(missing))
        sys.exit(1)
    # Assert values are not None to satisfy type checker
    assert required["TELEGRAM_BOT_TOKEN"] is not None
    assert required["ANTHROPIC_API_KEY"] is not None
    assert required["CHRISTIANVISION_CHANNEL"] is not None
    assert required["SHALTNOTKILL_CHANNEL"] is not None
    assert required["SOURCE_TEST_ID"] is not None
    return {
        "BOT_TOKEN": required["TELEGRAM_BOT_TOKEN"],
        "ANTHROPIC_API_KEY": required["ANTHROPIC_API_KEY"],
        "CHRISTIANVISION_CHANNEL": required["CHRISTIANVISION_CHANNEL"],
        "SHALTNOTKILL_CHANNEL": required["SHALTNOTKILL_CHANNEL"],
        "SOURCE_TEST_ID": required["SOURCE_TEST_ID"],
    }


def init_clients(
    env: Dict[str, str],
) -> Tuple[Client, Application, Anthropic, TelegramSender]:
    pyro = Client(
        "bot",
        api_id=int(os.getenv("TELEGRAM_API_ID", 0)),
        api_hash=os.getenv("TELEGRAM_API_HASH", ""),
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
    )
    builder = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN", ""))
    if AIORateLimiter is not None:
        try:
            builder = builder.rate_limiter(AIORateLimiter())
        except RuntimeError:
            pass
    ptb_app = builder.build()
    anthropic_client = Anthropic(api_key=env["ANTHROPIC_API_KEY"])
    sender = TelegramSender()
    return pyro, ptb_app, anthropic_client, sender


def get_channel_mapping(env: Dict[str, str]) -> Dict[int, str]:
    return {
        int(env["CHRISTIANVISION_CHANNEL"]): "christianvision",
        int(env["SHALTNOTKILL_CHANNEL"]): "shaltnotkill",
        int(env["SOURCE_TEST_ID"]): "test",
    }


###############################################################################
# Prompt / translation
###############################################################################


def build_prompt(html_text: str, channel: str, link: str) -> str:
    short = len(html_text.split()) < 7 or len(html_text) < 20
    intro = (
        "Translate the following HTML message without duplicating original message:"
        if short
        else ""
    )
    body = html_text if short else PROMPT_TEMPLATE.format(message_text=f"{html_text}")
    return f"{intro}\n\n{body}".strip()


async def translate_html(client: Anthropic, payload: Dict[str, Any]) -> str:
    prompt = build_prompt(payload["Html"], payload["Channel"], payload["Link"])
    resp = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1500,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


###############################################################################
# PTB‑worker (метаданные вложений)
###############################################################################
async def ptb_worker(ptb_app: Application, stop_event: asyncio.Event):
    """Fetch **all** Bot‑API data we can access: chat info + file info."""
    bot = ptb_app.bot
    ptb_log.info("PTB‑worker started")
    while not stop_event.is_set():
        req = await query_queue.get()
        ptb_log.info("Queue GET %s", req)

        # start meta with every attribute present in req
        meta: Dict[str, Any] = req.__dict__.copy()
        ptb_log.info("Initial meta: %s", meta)
        # ensure future not leaked to meta
        meta.pop("response", None)
        meta["chat"] = None
        meta["file"] = None

        # 1⃣ Chat‑level information ---------------------------------------
        try:
            chat_obj = await bot.get_chat(req.chat_id)
            meta["chat"] = chat_obj.to_dict()
            if getattr(chat_obj, "username", None):
                meta["chat_link"] = f"https://t.me/{chat_obj.username}"
            else:
                meta["chat_link"] = None
        except TelegramError as e:
            ptb_log.warning("get_chat failed for %s: %s", req.chat_id, e)
            meta["chat_error"] = str(e)

        # 2⃣ File‑level information (<=20 MB) -----------------------------
        if req.file_id:
            try:
                file_obj = await bot.get_file(req.file_id)
                meta["file"] = file_obj.to_dict()
                if file_obj.file_path:
                    meta["file_download_link"] = (
                        f"https://api.telegram.org/file/bot{bot.token}/{file_obj.file_path}"
                    )
            except TelegramError as e:
                err_msg = str(e)
                if "File is too big" in err_msg:
                    ptb_log.warning("File too big (>20MB) %s", req.file_id)
                    meta["file_error"] = "too_big"
                else:
                    ptb_log.warning("Bot API error: %s", err_msg)
                    meta["file_error"] = err_msg

        req.response.set_result(meta)


###############################################################################
# Pyrogram handler
###############################################################################


def register_handlers(
    pyro: Client, anthropic: Anthropic, sender: TelegramSender, mapping: Dict[int, str]
):
    max_size = 20 * 1024 * 1024

    @pyro.on_message(filters.channel & filters.chat(list(mapping.keys())))
    async def handle_message(_: Client, msg):
        pyro_log.info("=============================================")
        pyro_log.info("==== BEGIN HANDLING MESSAGE %s ====", msg.id)
        pyro_log.info("=============================================")
        target = mapping.get(msg.chat.id)
        if not target:
            return

        text = msg.text or msg.caption or ""
        # Determine small file_id
        file_id: str | None = None
        if msg.document and msg.document.file_size <= max_size:
            file_id = msg.document.file_id
        elif msg.photo and getattr(msg.photo, "file_size", 0) <= max_size:
            file_id = msg.photo.file_id
        elif msg.video and msg.video.file_size <= max_size:
            file_id = msg.video.file_id

        # Request metadata from PTB
        req = MetadataRequest(msg.chat.id, msg.id, file_id)
        # attach entities as plain dicts so PTB-worker returns them untouched
        raw_entities = msg.entities or msg.caption_entities or []
        req.message_entities = [
            e.to_dict() if hasattr(e, "to_dict") else e for e in raw_entities
        ]
        try:
            await query_queue.put(req)
            meta = await req.response
            html_text = entities_to_html(text, msg.entities or msg.caption_entities)
        except Exception as e:
            pyro_log.warning("!!! PTB worker failed: %s", e)
            meta = {}
            html_text = text

        # Build HTML text
        source_channel_link = (
            f'<a href="https://t.me/{msg.chat.username}">{msg.chat.title}</a>'
            if getattr(msg.chat, "username", None)
            else msg.chat.title
        )
        html_text = html_text + f"\n\nSource channel: {source_channel_link}"
        pyro_log.info("Generated HTML text for message %s: %s", msg.id, html_text)
        payload = {
            "Channel": msg.chat.title,
            "Text": text,
            "Html": html_text,
            "Link": f"https://t.me/{msg.chat.username}/{msg.id}",
            "Meta": meta
        }

        # Store source message in channel_logger cache after html_text is formed
        msg_id = getattr(msg, "id", None)
        if msg_id is None:
            msg_id = getattr(msg, "message_id", None)
        msg_data = {
            "message_id": msg_id,
            "date": getattr(msg, "date", None),
            "chat_title": getattr(msg.chat, "title", ""),
            "chat_username": getattr(msg.chat, "username", ""),
            "html": html_text,
        }
        store_message(msg.chat.id, msg_data)

        try:
            translated = await run_with_retries(translate_html, anthropic, payload)
            pyro_log.info("Translated message: %s", translated)
            # Store destination message inside TelegramSender
            cache_meta = {
                "mapping": mapping,
                "source_msg": msg,
                "source_html": html_text,
            }
            await run_with_retries(sender.send_message, translated, target, cache_meta)
            pyro_log.info("DONE %s → %s", msg.id, target)
        except Exception as exc:
            pyro_log.error("FAILED %s: %s", msg.id, exc)
        pyro_log.info("=============================================")
        pyro_log.info("==== END HANDLING MESSAGE %s ====", msg.id)
        pyro_log.info("=============================================")


###############################################################################
# Main                                                                        #
###############################################################################
async def main_async():
    logger.info("=== BOT STARTUP ===")
    env = load_config()
    pyro, ptb_app, anthropic, sender = init_clients(env)
    mapping = get_channel_mapping(env)

    register_handlers(pyro, anthropic, sender, mapping)
    # register_channel_logger(pyro)

    await ptb_app.initialize()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    asyncio.create_task(ptb_worker(ptb_app, stop_event))

    await pyro.start()
    pyro_log.info("Pyrogram started — Ctrl-C to exit")

    await stop_event.wait()

    pyro_log.info("Shutting down …")
    await ptb_app.stop()
    await pyro.stop()
    logger.info("=== BOT SHUTDOWN COMPLETE ===")


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Interrupted by user")


def format_channel_id(channel_id: str) -> Optional[str]:
    """Format channel ID for Telegram API"""
    if not channel_id:
        return None

    channel_id = str(channel_id).strip()

    # If it's already a username with @
    if channel_id.startswith("@"):
        return channel_id

    # If it's already a properly formatted channel ID
    if channel_id.startswith("-100") and channel_id[4:].isdigit():
        return channel_id

    # If it's a numeric ID (with or without leading minus)
    if channel_id.replace("-", "").isdigit():
        clean_id = channel_id.replace("-", "")
        return f"-100{clean_id}"

    # If it's a username without @
    if channel_id.isalnum() or "_" in channel_id:
        return f"@{channel_id}"

    logging.error("Invalid channel ID format: %s", channel_id)
    return None


def validate_channel(
    channel_id: str, channel_name: str, bot_token: Optional[str] = None
):
    """Validate that the bot has access to the channel"""
    if not channel_id:
        raise ValueError(f"No channel ID provided for {channel_name}")

    base_url = f"https://api.telegram.org/bot{bot_token}"

    try:
        logging.info(
            "Attempting to validate channel %s with ID: %s", channel_name, channel_id
        )
        response = requests.get(
            f"{base_url}/getChat", params={"chat_id": channel_id}, timeout=10
        )

        if response.status_code != 200:
            error_msg = response.json().get("description", "Unknown error")
            logging.error(
                "Failed to validate %s channel (%s): %s",
                channel_name,
                channel_id,
                error_msg,
            )
            logging.error("Please ensure:")
            logging.error("1. The channel ID is correct")
            logging.error("2. The bot is added to the channel as an admin")
            logging.error("3. The bot has these permissions:")
            logging.error("   - Post Messages")
            logging.error("   - Edit Messages")
            logging.error("   - Delete Messages")
            raise ValueError(f"Invalid channel configuration for {channel_name}")

        chat_info = response.json().get("result", {})
        logging.info("Successfully validated %s channel (%s)", channel_name, channel_id)
        logging.info(
            "Channel info: %s (%s)", chat_info.get("title"), chat_info.get("type")
        )

    except Exception as e:
        logging.error("Error validating %s channel: %s", channel_name, e)
        raise ValueError(
            f"Failed to validate {channel_name} channel configuration"
        ) from e
