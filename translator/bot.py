"""
Bidirectional Pyrogram ⇆ PTB relay bot.

• Pyrogram прослушивает исходные каналы.
• Для каждого сообщения формирует MetadataRequest и кладёт в очередь.
• Фоновый ptb_worker снимает запрос, вытаскивает максимум метаданных через Bot API
  и резолвит future.
• Pyrogram дожидается future, обогащает сообщение и переводит/пересылает.

"""

from __future__ import annotations

import os
import sys
import logging
# ensure project root is on PYTHONPATH when running this file directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


import asyncio
import html
import requests
import signal
import time
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from anthropic import Anthropic
from translator.config import CONFIG, PROMPT_TEMPLATE_PATH, load_prompt_template, CACHE_DIR
from translator.models import MetadataRequest, MessageEvent

from pyrogram import filters
from pyrogram.client import Client
from pyrogram.enums import MessageEntityType
from telegram.error import TelegramError
from telegram.ext import Application

# === Utility imports ===
from translator.utils.utils_html import entities_to_html
from translator.utils.utils_async import run_with_retries
from translator.utils.translation_utils import translate_html
from translator.utils.message_utils import (
    get_media_info,
    build_payload,
    log_and_store_message,
    extract_channel_info,
)
from translator.utils.channel_utils import TelegramAPI, format_channel_id, validate_channel

from translator.services.telegram_sender import TelegramSender
from translator.services.channel_logger import store_message
from translator.services.stats_logger import record_event, build_event_kwargs

# PTB optional rate limiter
try:
    from telegram.ext import AIORateLimiter  # type: ignore
except ImportError:  # pragma: no cover
    AIORateLimiter = None

query_queue = asyncio.Queue()


###############################################################################
# Logging
###############################################################################
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Ensure cache directory exists for logs
os.makedirs(CACHE_DIR, exist_ok=True)
LOG_FILE_PATH = os.path.join(CACHE_DIR, "bot.log")

try:
    # Set up file logging
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s — %(levelname)s — %(name)s — %(message)s",
        filename=LOG_FILE_PATH,   # Log file path in cache/
        filemode="a",             # Append mode
        encoding="utf-8"          # Ensure UTF-8 output
    )
except OSError as e:
    print(f"WARNING: Could not write to log file {LOG_FILE_PATH}: {e}")
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s — %(levelname)s — %(name)s — %(message)s"
    )

# Set up console logging (StreamHandler)
console = logging.StreamHandler()
console.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
formatter = logging.Formatter("%(asctime)s — %(levelname)s — %(name)s — %(message)s")
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

logger = logging.getLogger("MAIN")
pyro_log = logging.getLogger("PYRO")
ptb_log = logging.getLogger("PTB")

# Add a runtime check for log file writability and log to console if not writable
try:
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        pass
except OSError as e:
    logger = logging.getLogger()
    logger.error("OSError: write error to log file %s: %s. Logging to console only.", LOG_FILE_PATH, e)


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

        # 1 Chat‑level information ---------------------------------------
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

        # 2 File‑level information (<=20 MB) -----------------------------
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
        file_id, file_size_bytes, media_type = get_media_info(msg, max_size)

        # Request metadata from PTB
        req = MetadataRequest(msg.chat.id, msg.id, file_id)
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

        payload = build_payload(msg, html_text, meta)
        msg_id = log_and_store_message(msg, html_text)
        import json
        pyro_log.info("Payload data: %s", json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        pyro_log.info("Logged message id: %s", msg_id)
        translation_start = time.monotonic()
        retry_count = 0
        translation_time = None
        translated = ""
        exception_message = None
        api_error_code = None
        posting_success = False

        source_channel_id, source_channel_name, dest_channel_id, dest_channel_name = (
            extract_channel_info(msg, mapping, target)
        )

        try:
            # Translation with retries
            for attempt in range(1, 4):
                try:
                    translated = await translate_html(anthropic, payload)
                    translation_time = time.monotonic() - translation_start
                    retry_count = attempt - 1
                    break
                except Exception as e:
                    if attempt == 3:
                        raise
                    retry_count = attempt
                    await asyncio.sleep(2)
            pyro_log.info("Translated message: %s", translated)
            cache_meta = {
                "mapping": mapping,
                "source_msg": msg,
                "source_html": html_text,
            }
            post_start = time.monotonic()
            if (
                media_type == "photo"
                and meta.get("file_download_link")
                and len(translated) < 1024
            ):
                pyro_log.info("Detected photo message; ready to process photo with file download link.")
                posting_success, dest_channel_id_actual, api_error_code, exception_message = await run_with_retries(sender.send_photo_message,file_id,translated,target,cache_meta)
            else:
                posting_success, dest_channel_id_actual, api_error_code, exception_message = await run_with_retries(
                    sender.send_message,
                    translated,
                    target,
                    cache_meta,
                )

            dest_channel_id_to_log = (
                str(dest_channel_id_actual) if dest_channel_id_actual else ""
            )

            # --- Refactored event logging using dict-based pattern ---
            if record_event:
                event_kwargs = {
                    "event_type": "message",
                    "source_channel": source_channel_id,
                    "dest_channel": dest_channel_id_to_log,
                    "source_channel_name": source_channel_name,
                    "dest_channel_name": dest_channel_name,
                    "message_id": str(msg_id),
                    "media_type": media_type,
                    "file_size_bytes": file_size_bytes,
                    "original_size": len(text),
                    "translated_size": len(translated),
                    "translation_time": translation_time,
                    "retry_count": retry_count,
                    "posting_success": posting_success,
                    "api_error_code": api_error_code,
                    "exception_message": exception_message,
                    # "event": None,
                    # "edit_timestamp": None,
                    # "previous_size": None,
                    # "new_size": None,
                }
                # Remove None values
                event_kwargs = {k: v for k, v in event_kwargs.items() if v is not None}
                event_kwargs = build_event_kwargs(**event_kwargs)
                record_event(**event_kwargs)
            # --- end refactor ---

            pyro_log.info("DONE %s → %s", msg.id, target)
        except Exception as exc:
            exception_message = str(exc)
            api_error_code = getattr(exc, "status", None)
            # --- Refactored event logging using dict-based pattern ---
            if record_event:
                event_kwargs = {
                    "event_type": "message",
                    "source_channel": source_channel_id,
                    "dest_channel": dest_channel_id,
                    "source_channel_name": source_channel_name,
                    "dest_channel_name": dest_channel_name,
                    "message_id": str(msg_id),
                    "media_type": media_type,
                    "file_size_bytes": file_size_bytes,
                    "original_size": len(text),
                    "translated_size": len(translated) if translated else 0,
                    "translation_time": translation_time,
                    "retry_count": retry_count,
                    "posting_success": False,
                    "api_error_code": api_error_code,
                    "exception_message": exception_message,
                    # "event": None,
                    # "edit_timestamp": None,
                    # "previous_size": None,
                    # "new_size": None,
                }
                event_kwargs = {k: v for k, v in event_kwargs.items() if v is not None}
                event_kwargs = build_event_kwargs(**event_kwargs)
                record_event(**event_kwargs)
            # --- end refactor ---
            pyro_log.error("FAILED %s: %s", msg.id, exc)
        pyro_log.info("=============================================")
        pyro_log.info("==== END HANDLING MESSAGE %s ====", msg.id)
        pyro_log.info("=============================================")


###############################################################################
# Main                                                                        #
###############################################################################
async def main_async():
    logger.info("=== BOT STARTUP ===")
    # --- Session lock check ---
    session_file = "bot.session"
    if os.path.exists(session_file):
        try:
            conn = sqlite3.connect(session_file)
            conn.execute("PRAGMA quick_check")
            conn.close()
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                logger.error("Session file %s is locked. Stop all bots and delete this file before restarting.", session_file)
                raise
    # --- end session lock check ---

    pyro, ptb_app, anthropic, sender = init_clients()
    mapping = get_channel_mapping()

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


def init_clients() -> Tuple[Client, Application, Anthropic, TelegramSender]:
    pyro = Client(
        "bot",
        api_id=CONFIG.TELEGRAM_API_ID,
        api_hash=CONFIG.TELEGRAM_API_HASH,
        bot_token=CONFIG.TELEGRAM_BOT_TOKEN,
    )
    builder = Application.builder().token(CONFIG.TELEGRAM_BOT_TOKEN)
    if AIORateLimiter is not None:
        try:
            builder = builder.rate_limiter(AIORateLimiter())
        except RuntimeError:
            pass
    ptb_app = builder.build()
    anthropic_client = Anthropic(api_key=CONFIG.ANTHROPIC_API_KEY)
    sender = TelegramSender()
    return pyro, ptb_app, anthropic_client, sender


def get_channel_mapping() -> Dict[int, str]:
    return {
        int(CONFIG.CHANNELS["christianvision"]): "christianvision",
        int(CONFIG.CHANNELS["shaltnotkill"]): "shaltnotkill",
        int(CONFIG.CHANNELS["test"]): "test",
    }


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Interrupted by user")
