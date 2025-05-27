import os
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
import requests
import asyncio
from pathlib import Path
from flask_login import login_required  
import json  
import bleach

from anthropic import Anthropic
from translator.channel_logger import get_last_messages, check_deleted_messages
from translator import translator_reg  # Import for translation functions

admin_manager_bp = Blueprint("admin_manager_bp", __name__)  # renamed blueprint
TEMPLATE_PATH = Path(__file__).parent.parent / "translator" / "prompt_template.txt"


# Helper to get available channels from env
def get_available_channels():
    # Add EN channels as source (but translation will be impossible for them)
    channels = [
        {
            "name": "ChristianVision",
            "id": os.getenv("CHRISTIANVISION_CHANNEL"),
            "is_en": False,
        },
        {
            "name": "ShaltNotKill",
            "id": os.getenv("SHALTNOTKILL_CHANNEL"),
            "is_en": False,
        },
        {
            "name": "Test",
            "id": os.getenv("SOURCE_TEST_ID"),
            "is_en": False,
        },
        {
            "name": "ChristianVision EN",
            "id": os.getenv("CHRISTIANVISION_EN_CHANNEL_ID"),
            "is_en": True,
        },
        {
            "name": "ShaltNotKill EN",
            "id": os.getenv("SHALTNOTKILL_EN_CHANNEL_ID"),
            "is_en": True,
        },
    ]
    # Add test destination channel if set
    test_dest_id = os.getenv("TARGET_CHANNEL_ID")
    if test_dest_id:
        channels.append({
            "name": "Test Destination Channel",
            "id": test_dest_id,
            "is_en": True,
        })
    return channels

def get_target_channels():
    # You can expand this list as needed
    return [
        {
            "name": "ChristianVision EN",
            "id": os.getenv("CHRISTIANVISION_EN_CHANNEL_ID"),
            "type": "christianvision",
        },
        {
            "name": "ShaltNotKill EN",
            "id": os.getenv("SHALTNOTKILL_EN_CHANNEL_ID"),
            "type": "shaltnotkill",
        },
        {
            "name": "Test EN",
            "id": os.getenv("CHRISTIANVISION_EN_CHANNEL_ID"),
            "type": "test",
        },
    ]

@admin_manager_bp.route("/admin/manager", methods=["GET", "POST"])
@login_required
def channel_translate():
    channels = get_available_channels()
    target_channels = get_target_channels()
    selected_channel_id = request.form.get("source_channel") if request.method == "POST" else None
    selected_message_id = request.form.get("message_id") if request.method == "POST" else None
    selected_target_type = request.form.get("target_channel") if request.method == "POST" else None
    action = request.form.get("action") if request.method == "POST" else None
    translation_result = ""
    post_result = ""
    recent_messages = []
    selected_message_text = ""
    delete_result = ""

    # Always determine if selected_channel_is_en before any return
    selected_channel_is_en = False
    channels = get_available_channels()
    for ch in channels:
        if selected_channel_id == ch["id"]:
            selected_channel_is_en = ch.get("is_en", False)
            break

    # Ensure bot_token is set before any return or use
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Step 1: Select channel and fetch recent messages
    if selected_channel_id and not selected_message_id:
        # Optionally update cache before showing messages

        # Use channel_logger to fetch recent messages from cache
        last_msgs = get_last_messages(selected_channel_id)
        recent_messages = []
        for msg in reversed(last_msgs):
            msg_id = msg.get("message_id")
            html = msg.get("html", "")
            ts = msg.get("date", "")
            recent_messages.append({"id": msg_id, "html": html, "timestamp": ts})
        # Only keep the last 10 (should already be limited by logger, but for safety)
        recent_messages = recent_messages[:10]

    # Step 2: Select message and translate
    raw_html_result = ""
    rendered_html_result = ""
    if selected_channel_id and selected_message_id:
        # Handle delete action
        if action == "delete":
            try:
                print(f"[ADMIN] Attempting to delete message {selected_message_id} from channel {selected_channel_id}")
                url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
                resp = requests.post(url, data={
                    "chat_id": selected_channel_id,
                    "message_id": selected_message_id
                })
                if resp.status_code == 200 and resp.json().get("ok"):
                    print(f"[ADMIN] Message {selected_message_id} deleted from channel {selected_channel_id}")
                    delete_result = "Message deleted successfully."
                    # Remove from cache as well
                    last_msgs = get_last_messages(selected_channel_id)
                    filtered_msgs = [msg for msg in last_msgs if str(msg.get("message_id")) != str(selected_message_id)]
                    # Update the cache file
                    try:
                        from translator.channel_logger import CACHE_DIR
                        import json
                        cache_path = os.path.join(CACHE_DIR, "channel_cache.json")
                        # Load full cache, update, and save
                        if os.path.exists(cache_path):
                            with open(cache_path, "r", encoding="utf-8") as f:
                                cache = json.load(f)
                            if str(selected_channel_id) in cache:
                                cache[str(selected_channel_id)] = filtered_msgs
                                with open(cache_path, "w", encoding="utf-8") as f:
                                    json.dump(cache, f, ensure_ascii=False, indent=2)
                            else:
                                print(f"[WARN] Channel ID {selected_channel_id} not found in cache during delete.")
                        else:
                            print(f"[WARN] Cache file {cache_path} not found during delete.")
                    except Exception as e:
                        print(f"[WARN] Failed to update cache after delete: {e}")
                else:
                    print(f"[ADMIN][ERROR] Failed to delete message {selected_message_id} from channel {selected_channel_id}: {resp.text}")
                    delete_result = f"Failed to delete message: {resp.text}"
            except Exception as e:
                print(f"[ADMIN][ERROR] Exception while deleting message {selected_message_id} from channel {selected_channel_id}: {e}")
                delete_result = f"Error deleting message: {e}"
            # After deletion, refresh recent_messages using channel_logger cache
            last_msgs = get_last_messages(selected_channel_id)
            recent_messages = []
            for msg in reversed(last_msgs):
                msg_id = msg.get("message_id")
                html = msg.get("html", "")
                ts = msg.get("date", "")
                recent_messages.append({"id": msg_id, "html": html, "timestamp": ts})
            recent_messages = recent_messages[:10]
            # Reset selected_message_id so dropdown is updated and nothing is selected
            return render_template(
                "admin_manager.html",
                channels=channels,
                target_channels=target_channels,
                selected_channel_id=selected_channel_id,
                recent_messages=recent_messages,
                selected_message_id=None,
                selected_message_text="",
                translation_result="",
                raw_html_result="",
                rendered_html_result="",
                post_result=post_result,
                selected_target_type=selected_target_type,
                delete_result=delete_result,
                selected_channel_is_en=selected_channel_is_en,
            )

        # Fetch the selected message text using channel_logger cache
        last_msgs = get_last_messages(selected_channel_id)
        selected_message_text = ""
        chat_title = ""
        chat_username = ""
        for msg in last_msgs:
            if str(msg.get("message_id")) == str(selected_message_id):
                selected_message_text = msg.get("html", "")
                chat_title = msg.get("chat_title", "")
                chat_username = msg.get("chat_username", "")
                break

        # Only translate if action is "translate" or "post", and not for EN channels
        if selected_message_text and not selected_channel_is_en and (action == "translate" or action == "post"):
            try:
                print(f"[ADMIN] Translating message {selected_message_id} from channel {selected_channel_id}")
                # --- Use build_prompt and translate_html from translator_reg ---
                from translator.translator_reg import translate_html

                # Avoid HTML in payload, use plain text for source channel info
                if chat_username:
                    source_channel_link = f"https://t.me/{chat_username}"
                    html_with_source = f"{selected_message_text}\n\nSource channel: {chat_title} ({source_channel_link})"
                else:
                    html_with_source = f"{selected_message_text}\n\nSource channel: {chat_title}"
                payload = {
                    "Channel": chat_title,
                    "Text": selected_message_text,
                    "Html": html_with_source,
                    "Link": f"https://t.me/{chat_title}/{selected_message_id}",
                    "Meta": {},
                }
                anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
                print(f"[TRANSLATE] Calling translate_html with payload: {payload}")
                # Use the async translate_html from translator_reg
                translation_result = asyncio.run(
                    translate_html(anthropic_client, payload)
                )
                import re
                translation_result = re.sub(r'(</[a-z]+>)+$', '', translation_result)
                print(f"[TRANSLATE] Translation result: {translation_result[:200]}")
                raw_html_result = bleach.clean(translation_result, tags=["b", "i", "u", "a", "p", "br"], attributes={"a": ["href"]})
                rendered_html_result = translation_result
                print(f"[ADMIN] Translation completed for message {selected_message_id} from channel {selected_channel_id}")
            except Exception as e:
                print(f"[ADMIN][ERROR] Exception during translation of message {selected_message_id} from channel {selected_channel_id}: {e}")
                translation_result = f"Error during translation: {e}"
                raw_html_result = translation_result
                rendered_html_result = translation_result

    # Step 3: Post to target channel if requested
    if selected_channel_id and selected_message_id and selected_target_type and translation_result and action == "post":
        try:
            from translator.telegram_sender import TelegramSender
            sender = TelegramSender()
            ok = asyncio.run(sender.send_message(translation_result, selected_target_type))
            post_result = "Posted successfully." if ok else "Failed to post."
        except Exception as e:
            post_result = f"Error posting: {e}"

    return render_template(
        "admin_manager.html",
        channels=channels,
        target_channels=target_channels,
        selected_channel_id=selected_channel_id,
        recent_messages=recent_messages,
        selected_message_id=selected_message_id,
        selected_message_text=selected_message_text,
        translation_result=translation_result,
        raw_html_result=raw_html_result,
        rendered_html_result=rendered_html_result,
        post_result=post_result,
        selected_target_type=selected_target_type,
        delete_result=delete_result,
        selected_channel_is_en=selected_channel_is_en,
    )

from datetime import datetime

def datetimeformat(value, format='%H:%M %d/%m/%Y'):
    try:
        # Handle ISO 8601 string (e.g., 2025-05-25T12:46:24)
        if isinstance(value, str) and "T" in value:
            dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
            return dt.strftime(format)
        # Handle datetime object
        if isinstance(value, datetime):
            return value.strftime(format)
        # Handle timestamp (int/float/str)
        ts = float(value)
        return datetime.fromtimestamp(ts).strftime(format)
    except Exception:
        print(f"[ERROR] Failed to format datetime value: {value}")
        return value

@admin_manager_bp.route("/admin/cache", methods=["GET"])
@login_required
def show_cache():
    try:
        from translator.channel_logger import CACHE_DIR
    except ImportError:
        CACHE_DIR = "cache"
    cache_path = os.path.join(CACHE_DIR, "channel_cache.json")
    cache_data = {}
    error = None
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            # Convert timestamps to readable format if possible
            for messages in cache_data.values():
                for msg in messages:
                    ts = msg.get("date")
                    if ts:
                        msg["date_formatted"] = datetimeformat(ts)
                    else:
                        msg["date_formatted"] = ""
        except Exception as e:
            error = f"Failed to read cache: {e}"
    else:
        error = f"Cache file not found: {cache_path}"

    # Build channel_id -> channel_name mapping, including test destination channel
    channel_id_to_name = {}
    for ch in get_available_channels():
        if ch["id"]:
            channel_id_to_name[str(ch["id"])] = ch["name"]
    test_dest_id = os.getenv("TARGET_CHANNEL_ID")
    if test_dest_id and str(test_dest_id) not in channel_id_to_name:
        channel_id_to_name[str(test_dest_id)] = "Test Destination Channel"

    return render_template(
        "admin_cache_view.html",
        cache_data=cache_data,
        error=error,
        channel_id_to_name=channel_id_to_name,
    )

@admin_manager_bp.route("/admin/cache/update", methods=["POST"])
@login_required
def update_cache():
    """
    Update the cache for a given channel and message using channel_logger.store_message.
    Expects JSON payload: { "channel_id": ..., "message": {...} }
    """
    from translator.channel_logger import store_message

    data = request.get_json(silent=True)
    if not data or "channel_id" not in data or "message" not in data:
        return jsonify({"error": "Missing channel_id or message"}), 400

    channel_id = data["channel_id"]
    message_data = data["message"]

    try:
        store_message(channel_id, message_data)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500