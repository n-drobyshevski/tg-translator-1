import os
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
import requests
import asyncio
from pathlib import Path
from flask_login import login_required  
import bleach
from translator.channel_logger import get_last_messages, check_deleted_messages, store_message   # add store_message
import datetime                                                                                 # add datetime

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
            # use TARGET_CHANNEL_ID for the test destination
            "id": os.getenv("TARGET_CHANNEL_ID"),
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

    # pull the selected target channel _id_ from the form
    selected_target_channel_id = request.form.get("target_channel_id") if request.method == "POST" else None

    # initialize all result variables immediately
    translation_result = ""
    raw_html_result = ""
    rendered_html_result = ""
    post_result = ""          # <<< ensure this is defined unconditionally
    delete_result = ""
    recent_messages = []
    selected_message_text = ""

    # Avoid re-translating on post: restore previous translation
    if request.method == "POST" and action == "post":
        translation_result = request.form.get("translation_result", "")
        raw_html_result = request.form.get("raw_html_result", "")
        rendered_html_result = translation_result

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
        last_msgs = get_last_messages(selected_channel_id)
        recent_messages = []
        for msg in reversed(last_msgs):
            msg_id = msg.get("message_id")
            html   = msg.get("html", "")
            raw_ts = msg.get("date", "")
            # parse ISO-format, with or without offset
            try:
                dt = datetime.datetime.fromisoformat(raw_ts)
                ts = dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                ts = raw_ts
            recent_messages.append({"id": msg_id, "html": html, "timestamp": ts})
        # Only keep the last 10 (should already be limited by logger, but for safety)
        # recent_messages = recent_messages[:10]

    # Step 2: Select message and translate
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
                html   = msg.get("html", "")
                raw_ts = msg.get("date", "")
                try:
                    dt = datetime.datetime.fromisoformat(raw_ts)
                    ts = dt.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    ts = raw_ts
                recent_messages.append({"id": msg_id, "html": html, "timestamp": ts})
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

        edited_source = request.form.get("edited_source") if request.method == "POST" else None
        if edited_source:
            selected_message_text = edited_source

        # Allow either "translate" or "save-translate" to trigger translation
        if selected_message_text and not selected_channel_is_en and action in ["translate", "save-translate"]:
            try:
                print(f"[ADMIN] Translating message {selected_message_id} from channel {selected_channel_id}")
                # --- Use build_prompt and translate_html from translator_reg ---
                from translator.translator_reg import translate_html

                # Avoid HTML in payload, use plain text for source channel info
                if chat_username:
                    source_channel_link = f'<a href="https://t.me/{chat_username}">{chat_title}</a>'
                    html_with_source = f"{selected_message_text}\n\nSource channel: {source_channel_link}"
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
                print(f"[TRANSLATE] Translation result: {translation_result[:400]}")
                raw_html_result = bleach.clean(translation_result, tags=["b", "i", "u", "a", "p", "br"], attributes={"a": ["href"]})
                rendered_html_result = translation_result
                print(f"[ADMIN] Translation completed for message {selected_message_id} from channel {selected_channel_id}")
            except Exception as e:
                print(f"[ADMIN][ERROR] Exception during translation of message {selected_message_id} from channel {selected_channel_id}: {e}")
                translation_result = f"Error during translation: {e}"
                raw_html_result = translation_result
                rendered_html_result = translation_result

        # after translation, repopulate recent_messages for re-render
        last_msgs = get_last_messages(selected_channel_id)
        recent_messages = []
        for msg in reversed(last_msgs):
            msg_id = msg.get("message_id")
            html   = msg.get("html", "")
            raw_ts = msg.get("date", "")
            try:
                dt = datetime.datetime.fromisoformat(raw_ts)
                ts = dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                ts = raw_ts
            recent_messages.append({"id": msg_id, "html": html, "timestamp": ts})
        # recent_messages = recent_messages[:10]

    # Step 3: Post to target channel if requested
    if action == "post":
        print("Posting translation result to target channel")
        try:
            from translator.telegram_sender import TelegramSender
            sender = TelegramSender()
            if not selected_target_type:
                post_result = "Error posting: Target channel not found."
            else:
                print(f"[ADMIN][POST] Posting to channel type '{selected_target_type}'")
                message_to_send = raw_html_result or translation_result
                edit_mode = request.form.get("edit_mode")
                print(f"[DEBUG] edit_mode: {edit_mode}")
                if edit_mode:
                    # Edit the message matching source_channel_id and source_message_id
                    last_msgs = get_last_messages(selected_target_channel_id)
                    msg_id = None
                    for m in last_msgs:
                        if str(m.get("source_channel_id")) == str(selected_channel_id) and str(m.get("source_message_id")) == str(selected_message_id):
                            msg_id = m.get("message_id")
                            break
                    if msg_id:
                        ok = sender.edit_message(selected_target_channel_id, msg_id, message_to_send)
                        post_result = "Edited matching message." if ok else "Failed to edit message."
                    else:
                        post_result = "No matching message to edit in target channel."
                else:
                    ok = asyncio.run(
                        sender.send_message(message_to_send, selected_target_type)
                    )
                    post_result = "Posted successfully." if ok else "Failed to post."

                    if ok:
                        target_obj = next((ch for ch in target_channels if ch["type"] == selected_target_type), {})
                        msg_id = None
                        if hasattr(sender, "last_message_id"):
                            msg_id = sender.last_message_id
                        print(f"[DEBUG] Storing message in cache with id={msg_id}")
                        store_message(selected_target_channel_id, {
                            "message_id": msg_id,
                            "source_channel_id": selected_channel_id,
                            "source_message_id": selected_message_id,
                            "date": datetime.datetime.now(datetime.timezone.utc),
                            "chat_title": target_obj.get("name", ""),
                            "chat_username": "",
                            "html": message_to_send
                        })
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