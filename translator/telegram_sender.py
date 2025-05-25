import logging
import os
from dataclasses import dataclass
from typing import List

import requests
from dotenv import load_dotenv

try:
    from .channel_logger import store_message
except ImportError:
    from channel_logger import store_message

load_dotenv()


@dataclass
class ChannelConfig:
    channel_id: int
    bot_token: str


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

    async def send_message(self, text, target, meta=None):
        cfg = self.configs.get(target)
        if not cfg:
            logging.error("Unknown channel type: %s", target)
            return False
        if not cfg.channel_id:
            logging.error("No channel_id for %s", target)
            return False

        url = f"https://api.telegram.org/bot{cfg.bot_token}/sendMessage"
        chunks = self.split_message(text)
        sent_msg_id = None
        sent_chat_id = None
        for chunk in chunks:
            # Sanitize unsupported <p> tags: remove opening and replace closing with newline
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
                    return False
                result = r.json().get("result", {})
                sent_msg_id = result.get("message_id")
                sent_chat_id = result.get("chat", {}).get("id")
            except Exception as e:
                logging.error("Error sending to %s: %s", cfg.channel_id, e)
                return False

        logging.info("Successfully sent %d chunk(s) to %s", len(chunks), target)
        print(text)
        if meta is not None:
            mapping = meta.get("mapping")
            source_msg = meta.get("source_msg")
            # Try to get the destination channel id from mapping
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

        return True

    def _reconstruct_message(self, update: dict) -> str:
        from html import escape
        from pyrogram.enums import MessageEntityType

        msg = update.get("message", {})
        original_text = msg.get("text")
        if not original_text:
            return ""  # Return empty string if text is None or empty

        text_chars = list(original_text)
        entities = sorted(
            msg.get("entities", []), key=lambda e: e.get("offset", 0), reverse=True
        )

        for ent in entities:
            raw_type = ent.get("type")
            # Convert enum or string to lowercase string
            if hasattr(raw_type, "name"):
                typ = raw_type.name.lower()
            else:
                typ = str(raw_type).lower()

            s = ent.get("offset", 0)
            length = ent.get("length", 0)
            e = s + length
            segment = "".join(text_chars[s:e])

            if typ == "bold":
                segment = f"<b>{escape(segment)}</b>"
            elif typ == "italic":
                segment = f"<i>{escape(segment)}</i>"
            elif typ == "underline":
                segment = f"<u>{escape(segment)}</u>"
            elif typ == "strikethrough":
                segment = f"<s>{escape(segment)}</s>"
            elif typ == "spoiler":
                segment = f'<span class="tg-spoiler">{escape(segment)}</span>'
            elif typ == "text_link":
                url = ent.get("url", "")
                segment = f'<a href="{escape(url)}">{escape(segment)}</a>'
            elif typ == "url":
                segment = f'<a href="{escape(segment)}">{escape(segment)}</a>'

            text_chars[s:e] = [segment]

        return "".join(text_chars)
