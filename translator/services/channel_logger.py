import datetime
import json
import os
from typing import List, Dict, Any, Optional
from html import escape
from pyrogram.errors import MessageIdInvalid
from translator.config import CACHE_DIR, STORE_PATH, MESSAGES_LIMIT

os.makedirs(CACHE_DIR, exist_ok=True)


class ChannelCache:
    """Encapsulates channel message caching logic."""

    def __init__(self):
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, List[Dict[str, Any]]]:
        if os.path.exists(STORE_PATH):
            try:
                with open(STORE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save(self):
        with open(STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def store_message(self, channel_id: str, message_data: Dict[str, Any]):
        """Store message in the channel cache."""
        channel_id = str(channel_id)
        # Format date for JSON
        if "date" in message_data and isinstance(
            message_data["date"], datetime.datetime
        ):
            message_data["date"] = message_data["date"].isoformat()
        # Ensure presence of chat_title and chat_username
        message_data.setdefault("chat_title", "")
        message_data.setdefault("chat_username", "")
        # sanitize html before storing
        raw = message_data.get("html", "")
        safe_html = escape(raw)  # now all <,>,& etc. are escaped
        message_data["html"] = safe_html
        message_data.pop("entities", None)
        if channel_id not in self.cache:
            self.cache[channel_id] = []
        self.cache[channel_id].append(message_data)
        if len(self.cache[channel_id]) > MESSAGES_LIMIT:
            self.cache[channel_id] = self.cache[channel_id][-MESSAGES_LIMIT:]
        self.save()

    def get_last_messages(self, channel_id: str) -> List[Dict[str, Any]]:
        return self.cache.get(str(channel_id), [])

    def check_deleted_messages(self, client):
        updated = {}
        for channel_id, messages in self.cache.items():
            valid_messages = []
            for msg in messages:
                try:
                    client.get_messages(int(channel_id), msg["message_id"])
                    valid_messages.append(msg)
                except MessageIdInvalid:
                    print(
                        f"Message {msg['message_id']} deleted from channel {channel_id}"
                    )
            if valid_messages:
                updated[channel_id] = valid_messages
        self.cache = updated
        self.save()


# Provide a global instance
channel_cache = ChannelCache()


def store_message(channel_id, message_data):
    channel_cache.store_message(channel_id, message_data)


def get_last_messages(channel_id):
    return channel_cache.get_last_messages(channel_id)


# add this so admin_manager can import it
def check_deleted_messages(client):
    channel_cache.check_deleted_messages(client)
