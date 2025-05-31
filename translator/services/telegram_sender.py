import logging
import os
from typing import List

import requests
from dotenv import load_dotenv
from translator.models import ChannelConfig

try:
    from .channel_logger import store_message
except ImportError:
    from translator.services.channel_logger import store_message

load_dotenv()

# Load all channel configs once
CHANNEL_CONFIGS = {
    "christianvision": ChannelConfig(
        channel_id=os.getenv("CHRISTIANVISION_EN_CHANNEL_ID", 0),
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
    ),
    "shaltnotkill": ChannelConfig(
        channel_id=os.getenv("SHALTNOTKILL_EN_CHANNEL_ID", 0),
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
    ),
    "test": ChannelConfig(
        channel_id=os.getenv("TARGET_CHANNEL_ID", 0),
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
    ),
}

# Reuse one HTTP session
_SESSION = requests.Session()


class TelegramSender:
    def __init__(self):
        self.configs = CHANNEL_CONFIGS
        self.MAX_MESSAGE_LENGTH = 4096

    def split_message(self, text: str) -> List[str]:
        """Split into <=4096‑char chunks, preserving lines."""
        if len(text) <= self.MAX_MESSAGE_LENGTH:
            return [text]
        messages, current = [], ""
        for line in text.split("\n"):
            if len(current) + len(line) + 1 > self.MAX_MESSAGE_LENGTH:
                messages.append(current.rstrip("\n"))
                current = line + "\n"
            else:
                current += line + "\n"
        if current:
            messages.append(current.rstrip("\n"))
        return messages

    async def send_message(
        self,
        text,
        target,
        meta=None,
        *,
        translation_time: float = None,
        retry_count: int = 0,
        api_error_code: int = None,
        exception_message: str = None,
        media_type: str = None,
        file_size_bytes: int = None,
        event: str = None,
        edit_timestamp: str = None,
        previous_size: int = None,
        new_size: int = None
    ):
        cfg = self.configs.get(target)
        if not cfg:
            logging.error("Unknown channel type: %s", target)
            return False, None
        if not cfg.channel_id:
            logging.error("No channel_id for %s", target)
            return False, None

        url = f"https://api.telegram.org/bot{cfg.bot_token}/sendMessage"
        chunks = self.split_message(text)
        sent_msg_id = None
        sent_chat_id = None
        posting_success = False
        # Stats extraction
        source_channel = None
        dest_channel = str(cfg.channel_id)
        original_size = len(meta.get("source_html", "")) if meta and meta.get("source_html") else len(text)
        translated_size = len(text)
        message_id = None

        # Try to extract media_type and file_size_bytes from meta if not provided
        if not media_type and meta is not None:
            source_msg = meta.get("source_msg")
            if source_msg:
                if hasattr(source_msg, "photo") and getattr(source_msg, "photo", None):
                    media_type = "photo"
                    file_size_bytes = getattr(source_msg.photo, "file_size", None)
                elif hasattr(source_msg, "video") and getattr(source_msg, "video", None):
                    media_type = "video"
                    file_size_bytes = getattr(source_msg.video, "file_size", None)
                elif hasattr(source_msg, "document") and getattr(source_msg, "document", None):
                    media_type = "doc"
                    file_size_bytes = getattr(source_msg.document, "file_size", None)
                else:
                    media_type = "text"
                    file_size_bytes = None
                # Try to get source_channel
                if hasattr(source_msg, "chat"):
                    source_channel = str(getattr(source_msg.chat, "id", None))
                message_id = getattr(source_msg, "id", None) or getattr(source_msg, "message_id", None)
        if not source_channel and meta is not None:
            source_channel = str(meta.get("source_channel_id", ""))

        for chunk in chunks:
            sanitized_chunk = chunk.replace("<p>", "").replace("</p>", "")
            logging.info(
                "Sending chunk to %s (chat_id %s)…", target, cfg.channel_id
            )
            try:
                r = _SESSION.post(
                    url,
                    json={
                        "chat_id": cfg.channel_id,
                        "text": sanitized_chunk,
                        "parse_mode": "HTML",
                    },
                    timeout=10,
                )
                if r.status_code != 200:
                    desc = r.json().get("description", r.text)
                    logging.error("Failed to send to %s: %s", cfg.channel_id, desc)
                    api_error_code = r.status_code
                    exception_message = desc
                    posting_success = False
                    return False, None
                result = r.json().get("result", {})
                sent_msg_id = result.get("message_id")
                sent_chat_id = result.get("chat", {}).get("id")
                posting_success = True
            except Exception as e:
                logging.error("Error sending to %s: %s", cfg.channel_id, e)
                posting_success = False
                exception_message = str(e)
                return False, None

        logging.info("Successfully sent %d chunk(s) to %s", len(chunks), target)
        print(text)
        if meta is not None:
            mapping = meta.get("mapping")
            source_msg = meta.get("source_msg")
            dest_channel_id = None
            for k, v in (mapping or {}).items():
                if v == target:
                    dest_channel_id = k
                    break
            if dest_channel_id:
                dest_msg_data = {
                    "message_id": sent_msg_id,
                    "date": getattr(source_msg, "date", None) if source_msg else None,
                    "chat_title": target,
                    "chat_username": "",
                    "html": text,
                    "source_channel_id": (
                        getattr(source_msg.chat, "id", None) if source_msg else "None"
                    ),
                    "source_message_id": (
                        getattr(source_msg, "message_id", None)
                        or getattr(source_msg, "id", None)
                    ) if source_msg else "None",
                }
                store_message(sent_chat_id, dest_msg_data)

        return posting_success, sent_chat_id

    def edit_message(
        self,
        channel_id,
        message_id,
        text,
        *,
        translation_time: float = None,
        retry_count: int = 0,
        api_error_code: int = None,
        exception_message: str = None,
        media_type: str = None,
        file_size_bytes: int = None,
        event: str = "message_edit",
        edit_timestamp: str = None,
        previous_size: int = None,
        new_size: int = None,
        source_channel: str = None,
        dest_channel: str = None
    ):
        """
        Edit a message in a Telegram channel by channel_id and message_id.
        Returns True if successful, False otherwise.
        """
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
        sanitized_text = text.replace("<p>", "").replace("</p>", "")
        payload = {
            "chat_id": channel_id,
            "message_id": message_id,
            "text": sanitized_text,
            "parse_mode": "HTML"
        }
        posting_success = False
        try:
            resp = _SESSION.post(url, data=payload, timeout=10)
            if resp.status_code == 200 and resp.json().get("ok"):
                posting_success = True
                # No record_event here
                return True
            else:
                logging.error("Failed to edit message %s in %s: %s", message_id, channel_id, resp.text)
                posting_success = False
                api_error_code = resp.status_code
                exception_message = resp.text
                # No record_event here
                return False
        except Exception as e:
            logging.error("Exception editing message %s in %s: %s", message_id, channel_id, e)
            posting_success = False
            exception_message = str(e)
            # No record_event here
            return False
