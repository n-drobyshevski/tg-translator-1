import os
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
import requests
import asyncio
from pathlib import Path
from flask_login import login_required  # add this import

from anthropic import Anthropic
from translator.channel_logger import get_last_messages, check_deleted_messages
from translator import translator_reg  # Import for translation functions

admin_channel_translate_bp = Blueprint("admin_channel_translate_bp", __name__)
TEMPLATE_PATH = Path(__file__).parent.parent / "translator" / "prompt_template.txt"


# Helper to get available channels from env
def get_available_channels():
    # Add EN channels as source (but translation will be impossible for them)
    return [
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

@admin_channel_translate_bp.route("/admin/channel_translate", methods=["GET", "POST"])
@login_required
def channel_translate():
    channels = get_available_channels()
    target_channels = get_target_channels()
    selected_channel_id = request.form.get("source_channel") if request.method == "POST" else None
    selected_message_id = request.form.get("message_id") if request.method == "POST" else None
    selected_target_type = request.form.get("target_channel") if request.method == "POST" else None
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
            text = msg.get("text", "")
            ts = msg.get("date", "")
            recent_messages.append({"id": msg_id, "text": text, "timestamp": ts})
        # Only keep the last 10 (should already be limited by logger, but for safety)
        recent_messages = recent_messages[:10]

    # Step 2: Select message and translate
    raw_html_result = ""
    rendered_html_result = ""
    if selected_channel_id and selected_message_id:
        # Handle delete action
        if request.form.get("action") == "delete":
            try:
                url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
                resp = requests.post(url, data={
                    "chat_id": selected_channel_id,
                    "message_id": selected_message_id
                })
                if resp.status_code == 200 and resp.json().get("ok"):
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
                    delete_result = f"Failed to delete message: {resp.text}"
            except Exception as e:
                delete_result = f"Error deleting message: {e}"
            # After deletion, refresh recent_messages using channel_logger cache
            last_msgs = get_last_messages(selected_channel_id)
            recent_messages = []
            for msg in reversed(last_msgs):
                msg_id = msg.get("message_id")
                text = msg.get("text", "")
                ts = msg.get("date", "")
                recent_messages.append({"id": msg_id, "text": text, "timestamp": ts})
            recent_messages = recent_messages[:10]
            # Reset selected_message_id so dropdown is updated and nothing is selected
            return render_template(
                "admin_channel_translate.html",
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
        for msg in last_msgs:
            if str(msg.get("message_id")) == str(selected_message_id):
                selected_message_text = msg.get("text", "")
                break

        # Translate
        if selected_message_text and not selected_channel_is_en:
            try:
                # Use build_prompt and translate_html from translator_reg
                chat_title = ""
                chat_username = ""
                # Try to get chat_title and username from the cache if available
                for msg in last_msgs:
                    if str(msg.get("message_id")) == str(selected_message_id):
                        chat_title = msg.get("chat_title", "")
                        # chat_username may not be present, so use empty string if missing
                        chat_username = msg.get("chat_username", "")
                        break
                if not chat_title:
                    chat_title = selected_channel_id
                # Build source channel link (like in relay bot)
                if chat_username:
                    source_channel_link = f'<a href="https://t.me/{chat_username}">{chat_title}</a>'
                else:
                    source_channel_link = chat_title
                # Append source at the end of the message
                html_with_source = f"{selected_message_text}\n\nSource channel: {source_channel_link}"
                payload = {
                    "Channel": chat_title,
                    "Text": selected_message_text,
                    "Html": html_with_source,
                    "Link": f"https://t.me/{chat_title}/{selected_message_id}",
                    "Meta": {},
                }
                anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
                translation_result = asyncio.run(
                    translator_reg.translate_html(anthropic_client, payload)
                )
                import re
                translation_result = re.sub(r'(</[a-z]+>)+$', '', translation_result)
                raw_html_result = translation_result
                rendered_html_result = translation_result
            except Exception as e:
                translation_result = f"Error during translation: {e}"
                raw_html_result = translation_result
                rendered_html_result = translation_result

    # Step 3: Post to target channel if requested
    if selected_channel_id and selected_message_id and selected_target_type and translation_result:
        try:
            from translator.telegram_sender import TelegramSender
            sender = TelegramSender()
            ok = asyncio.run(sender.send_message(translation_result, selected_target_type))
            post_result = "Posted successfully." if ok else "Failed to post."
        except Exception as e:
            post_result = f"Error posting: {e}"

    return render_template(
        "admin_channel_translate.html",
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
