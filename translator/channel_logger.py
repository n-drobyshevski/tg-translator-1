# channel_logger.py
from pyrogram import filters
import datetime
import json
import os
from pyrogram.errors import MessageIdInvalid

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
STORE_PATH = os.path.join(CACHE_DIR, "channel_cache.json")

# Загрузка кэша из файла или инициализация
if os.path.exists(STORE_PATH):
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}
else:
    cache = {}

MESSAGES_LIMIT = 9 

# Сохраняет сообщение в кэш (оставляет только 5 последних)
def store_message(channel_id, message_data):
    channel_id = str(channel_id)

    # Convert datetime objects to isoformat strings for JSON serialization
    if "date" in message_data and isinstance(message_data["date"], datetime.datetime):
        message_data["date"] = message_data["date"].isoformat()

    # Ensure chat_title and chat_username are present in message_data
    if "chat_title" not in message_data or not message_data["chat_title"]:
        message_data["chat_title"] = ""
    if "chat_username" not in message_data:
        chat_obj = message_data.get("chat")
        if chat_obj and isinstance(chat_obj, dict):
            message_data["chat_username"] = chat_obj.get("username", "")
        else:
            message_data["chat_username"] = ""

    # Only store HTML version, ignore entities
    if "html" not in message_data:
        text = message_data.get("text", "")
        message_data["html"] = text or ""

    # Remove entities if present
    if "entities" in message_data:
        message_data.pop("entities")

    if channel_id not in cache:
        cache[channel_id] = []

    cache[channel_id].append(message_data)

    if len(cache[channel_id]) > MESSAGES_LIMIT:
        cache[channel_id] = cache[channel_id][-MESSAGES_LIMIT:]

    for msgs in cache.values():
        for msg in msgs:
            if "date" in msg and isinstance(msg["date"], datetime.datetime):
                msg["date"] = msg["date"].isoformat()
            # Remove entities from all cached messages
            if "entities" in msg:
                msg.pop("entities")

    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    try:
        check_deleted_messages(None)
    except Exception as e:
        print(f"[INFO] check_deleted_messages failed: {e}")


# Регистрирует обработчики Pyrogram
def register_channel_logger(app):
    # Обработка новых сообщений из каналов
    @app.on_message(filters.channel)
    def handle_channel_post(client, message):
        # Pyrogram Message object uses 'id' for message id, not 'message_id'
        msg_id = getattr(message, "message_id", None)
        if msg_id is None:
            msg_id = getattr(message, "id", None)

        msg_data = {
            "message_id": msg_id,
            "text": message.text or message.caption or "[медиа]",
            "date": message.date.isoformat(),
            "chat_title": message.chat.title,
            "chat_username": getattr(message.chat, "username", ""),
            "entities": getattr(message, "entities", None) or getattr(message, "caption_entities", None),
            # Optionally, you can add more fields if needed
        }

        print(
            f"Сохраняем сообщение из {message.chat.title}: {msg_data['text'][:30]}..."
        )
        store_message(message.chat.id, msg_data)

    # Обработка редактирования сообщений
    @app.on_edited_message(filters.channel)
    def handle_channel_edit(client, message):
        channel_id = str(message.chat.id)
        # Use .id if .message_id is not present (Pyrogram Message uses .id)
        msg_id = getattr(message, "message_id", None)
        if msg_id is None:
            msg_id = getattr(message, "id", None)

        if channel_id not in cache:
            # No messages for this channel, nothing to update
            return

        found = False
        for msg in cache[channel_id]:
            if msg["message_id"] == msg_id:
                msg["text"] = message.text or message.caption or "[медиа]"
                msg["date"] = (
                    message.edit_date.isoformat()
                    if message.edit_date
                    else message.date.isoformat()
                )
                print(
                    f"Обновлено сообщение {msg_id} в {message.chat.title}: {msg['text'][:30]}"
                )
                found = True
                break

        if not found:
            # No matching message found, just skip
            return

        try:
            with open(STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except FileNotFoundError:
            print(f"[INFO] Cache file {STORE_PATH} not found during edit event, skipping.")
            # Just continue if file is missing


# Проверяет, были ли сообщения удалены, и очищает кэш
def check_deleted_messages(client):
    updated = {}
    for channel_id, messages in cache.items():
        valid_messages = []
        for msg in messages:
            try:
                client.get_messages(int(channel_id), msg["message_id"])
                valid_messages.append(msg)
            except MessageIdInvalid:
                print(f"Сообщение {msg['message_id']} удалено из канала {channel_id}")
            except FileNotFoundError:
                # If the file for this channel_id is missing, skip silently
                continue
        if valid_messages:
            updated[channel_id] = valid_messages

    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)

    print("Проверка на удалённые сообщения завершена.")


# Получает последние сообщения из кэша (для ручного вызова)
def get_last_messages(channel_id):
    channel_id = str(channel_id)
    return cache.get(channel_id, [])
