import os
from flask import Blueprint, render_template, request
import requests
import asyncio
from flask_login import login_required
import bleach
import datetime
from anthropic import Anthropic
from translator.services.channel_logger import get_last_messages, store_message
from translator.config import CACHE_DIR
from translator import bot

admin_manager_bp = Blueprint("admin_manager_bp", __name__)


def fetch_channel_title(channel_id, bot_token=None):
    """Fetch the Telegram channel's current title via Bot API."""
    if not channel_id:
        return {"title": str(channel_id), "username": ""}
    if not bot_token:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    url = f"https://api.telegram.org/bot{bot_token}/getChat"
    try:
        resp = requests.get(url, params={"chat_id": channel_id}, timeout=6)
        if resp.status_code == 200 and resp.json().get("ok"):
            result = resp.json()["result"]
            title = result.get("title", "") or str(channel_id)
            username = result.get("username", "")
            return {"title": title, "username": username}
    except Exception as e:
        print(f"[WARN] Could not fetch channel info for {channel_id}: {e}")
    return {"title": str(channel_id), "username": ""}


def get_available_channels():
    """Build a list of available channels with real Telegram titles."""
    ids = [
        os.getenv("CHRISTIANVISION_CHANNEL"),
        os.getenv("SHALTNOTKILL_CHANNEL"),
        os.getenv("SOURCE_TEST_ID"),
        os.getenv("CHRISTIANVISION_EN_CHANNEL_ID"),
        os.getenv("SHALTNOTKILL_EN_CHANNEL_ID"),
        os.getenv("TARGET_CHANNEL_ID"),
    ]
    ids = [i for i in ids if i]
    seen = set()
    channels = []
    for id_ in ids:
        if id_ in seen:
            continue
        seen.add(id_)
        info = fetch_channel_title(id_)
        is_en = id_ in [
            os.getenv("CHRISTIANVISION_EN_CHANNEL_ID"),
            os.getenv("SHALTNOTKILL_EN_CHANNEL_ID"),
            os.getenv("TARGET_CHANNEL_ID"),
        ]
        channels.append(
            {
                "name": info["title"] or id_,
                "id": id_,
                "is_en": is_en,
                "username": info["username"],
            }
        )
    return channels


def get_target_channels():
    return [
        {
            "name": fetch_channel_title(os.getenv("CHRISTIANVISION_EN_CHANNEL_ID"))[
                "title"
            ],
            "id": os.getenv("CHRISTIANVISION_EN_CHANNEL_ID"),
            "type": "christianvision",
        },
        {
            "name": fetch_channel_title(os.getenv("SHALTNOTKILL_EN_CHANNEL_ID"))[
                "title"
            ],
            "id": os.getenv("SHALTNOTKILL_EN_CHANNEL_ID"),
            "type": "shaltnotkill",
        },
        {
            "name": fetch_channel_title(os.getenv("TARGET_CHANNEL_ID"))["title"],
            "id": os.getenv("TARGET_CHANNEL_ID"),
            "type": "test",
        },
    ]


@admin_manager_bp.route("/admin/manager", methods=["GET", "POST"])
@login_required
def channel_translate():
    channels = get_available_channels()
    target_channels = get_target_channels()
    selected_channel_id = (
        request.form.get("source_channel") if request.method == "POST" else None
    )
    selected_message_id = (
        request.form.get("message_id") if request.method == "POST" else None
    )
    selected_target_type = (
        request.form.get("target_channel") if request.method == "POST" else None
    )
    action = request.form.get("action") if request.method == "POST" else None
    selected_target_channel_id = (
        request.form.get("target_channel_id") if request.method == "POST" else None
    )

    translation_result = ""
    raw_html_result = ""
    rendered_html_result = ""
    post_result = ""
    delete_result = ""
    recent_messages = []
    selected_message_text = ""

    # NEW: custom message state
    message_option = request.form.get("message_option")
    custom_message_text = request.form.get("custom_message_text", "")

    if request.method == "POST" and action == "post":
        translation_result = request.form.get("translation_result", "")
        raw_html_result = request.form.get("raw_html_result", "")
        rendered_html_result = translation_result

    selected_channel_is_en = False
    for ch in channels:
        if selected_channel_id == ch["id"]:
            selected_channel_is_en = ch.get("is_en", False)
            break

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Step 1: Select channel and fetch recent messages
    if (
        selected_channel_id
        and not selected_message_id
        and not (message_option == "custom" and action == "translate_custom")
    ):
        last_msgs = get_last_messages(selected_channel_id)
        recent_messages = []
        for msg in reversed(last_msgs):
            msg_id = msg.get("message_id")
            html = msg.get("html", "")
            raw_ts = msg.get("date", "")
            try:
                dt = datetime.datetime.fromisoformat(raw_ts)
                ts = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                ts = raw_ts
            recent_messages.append({"id": msg_id, "html": html, "timestamp": ts})

    # ---- CUSTOM MESSAGE HANDLING ----
    if (
        selected_channel_id
        and message_option == "custom"
        and action == "translate_custom"
        and custom_message_text
    ):
        selected_message_text = custom_message_text.strip()
        selected_message_id = None
        chat_title = ""
        chat_username = ""
        for ch in channels:
            if selected_channel_id == ch["id"]:
                chat_title = ch.get("name", "")
                chat_username = ch.get("username", "")
                break
        if not selected_channel_is_en and selected_message_text:
            try:
                from translator.bot import translate_html

                if chat_username:
                    source_channel_link = (
                        f'<a href="https://t.me/{chat_username}">{chat_title}</a>'
                    )
                    html_with_source = f"{selected_message_text}\n\nSource channel: {source_channel_link}"
                else:
                    html_with_source = (
                        f"{selected_message_text}\n\nSource channel: {chat_title}"
                    )
                payload = {
                    "Channel": chat_title,
                    "Text": selected_message_text,
                    "Html": html_with_source,
                    "Link": f"https://t.me/{chat_title}/0",
                    "Meta": {},
                }
                anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
                translation_result = asyncio.run(
                    translate_html(anthropic_client, payload)
                )
                import re

                translation_result = re.sub(r"(</[a-z]+>)+$", "", translation_result)
                raw_html_result = bleach.clean(
                    translation_result,
                    tags=["b", "i", "u", "a", "p", "br"],
                    attributes={"a": ["href"]},
                )
                rendered_html_result = translation_result
            except Exception as e:
                translation_result = f"Error during translation: {e}"
                raw_html_result = translation_result
                rendered_html_result = translation_result
        last_msgs = get_last_messages(selected_channel_id)
        recent_messages = []
        for msg in reversed(last_msgs):
            msg_id = msg.get("message_id")
            html = msg.get("html", "")
            raw_ts = msg.get("date", "")
            try:
                dt = datetime.datetime.fromisoformat(raw_ts)
                ts = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                ts = raw_ts
            recent_messages.append({"id": msg_id, "html": html, "timestamp": ts})

    # ---- EXISTING MESSAGE HANDLING ----
    if (
        selected_channel_id
        and selected_message_id
        and (not message_option or message_option == "existing")
    ):
        if action == "delete":
            try:
                print(
                    f"[ADMIN] Attempting to delete message {selected_message_id} from channel {selected_channel_id}"
                )
                url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
                resp = requests.post(
                    url,
                    data={
                        "chat_id": selected_channel_id,
                        "message_id": selected_message_id,
                    },
                )
                if resp.status_code == 200 and resp.json().get("ok"):
                    delete_result = "Message deleted successfully."
                    last_msgs = get_last_messages(selected_channel_id)
                    filtered_msgs = [
                        msg
                        for msg in last_msgs
                        if str(msg.get("message_id")) != str(selected_message_id)
                    ]
                    try:
                        import json

                        cache_path = os.path.join(CACHE_DIR, "channel_cache.json")
                        if os.path.exists(cache_path):
                            with open(cache_path, "r", encoding="utf-8") as f:
                                cache = json.load(f)
                            if str(selected_channel_id) in cache:
                                cache[str(selected_channel_id)] = filtered_msgs
                                with open(cache_path, "w", encoding="utf-8") as f:
                                    json.dump(cache, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        print(f"[WARN] Failed to update cache after delete: {e}")
                else:
                    delete_result = f"Failed to delete message: {resp.text}"
            except Exception as e:
                delete_result = f"Error deleting message: {e}"
            last_msgs = get_last_messages(selected_channel_id)
            recent_messages = []
            for msg in reversed(last_msgs):
                msg_id = msg.get("message_id")
                html = msg.get("html", "")
                raw_ts = msg.get("date", "")
                try:
                    dt = datetime.datetime.fromisoformat(raw_ts)
                    ts = dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    ts = raw_ts
                recent_messages.append({"id": msg_id, "html": html, "timestamp": ts})
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
                custom_message_text=custom_message_text,
                message_option=message_option,
            )

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

        edited_source = (
            request.form.get("edited_source") if request.method == "POST" else None
        )
        if edited_source:
            selected_message_text = edited_source

        if (
            selected_message_text
            and not selected_channel_is_en
            and action in ["translate", "save-translate"]
        ):
            try:
                from translator.bot import translate_html

                if chat_username:
                    source_channel_link = (
                        f'<a href="https://t.me/{chat_username}">{chat_title}</a>'
                    )
                    html_with_source = f"{selected_message_text}\n\nSource channel: {source_channel_link}"
                else:
                    html_with_source = (
                        f"{selected_message_text}\n\nSource channel: {chat_title}"
                    )
                payload = {
                    "Channel": chat_title,
                    "Text": selected_message_text,
                    "Html": html_with_source,
                    "Link": f"https://t.me/{chat_title}/{selected_message_id}",
                    "Meta": {},
                }
                anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
                translation_result = asyncio.run(
                    translate_html(anthropic_client, payload)
                )
                import re

                translation_result = re.sub(r"(</[a-z]+>)+$", "", translation_result)
                raw_html_result = bleach.clean(
                    translation_result,
                    tags=["b", "i", "u", "a", "p", "br"],
                    attributes={"a": ["href"]},
                )
                rendered_html_result = translation_result
            except Exception as e:
                translation_result = f"Error during translation: {e}"
                raw_html_result = translation_result
                rendered_html_result = translation_result

        last_msgs = get_last_messages(selected_channel_id)
        recent_messages = []
        for msg in reversed(last_msgs):
            msg_id = msg.get("message_id")
            html = msg.get("html", "")
            raw_ts = msg.get("date", "")
            try:
                dt = datetime.datetime.fromisoformat(raw_ts)
                ts = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                ts = raw_ts
            recent_messages.append({"id": msg_id, "html": html, "timestamp": ts})

    # Step 3: Post to target channel if requested
    if action == "post":
        try:
            from translator.services.telegram_sender import TelegramSender

            sender = TelegramSender()
            if not selected_target_type:
                post_result = "Error posting: Target channel not found."
            else:
                message_to_send = raw_html_result or translation_result
                edit_mode = request.form.get("edit_mode")
                if edit_mode:
                    last_msgs = get_last_messages(selected_target_channel_id)
                    msg_id = None
                    for m in last_msgs:
                        if str(m.get("source_channel_id")) == str(
                            selected_channel_id
                        ) and str(m.get("source_message_id")) == str(
                            selected_message_id
                        ):
                            msg_id = m.get("message_id")
                            break
                    if msg_id:
                        ok = sender.edit_message(
                            selected_target_channel_id, msg_id, message_to_send
                        )
                        post_result = (
                            "Edited matching message."
                            if ok
                            else "Failed to edit message."
                        )
                    else:
                        post_result = "No matching message to edit in target channel."
                else:
                    ok = asyncio.run(
                        sender.send_message(message_to_send, selected_target_type)
                    )
                    post_result = "Posted successfully." if ok else "Failed to post."

                    if ok:
                        target_obj = next(
                            (
                                ch
                                for ch in target_channels
                                if ch["type"] == selected_target_type
                            ),
                            {},
                        )
                        msg_id = None
                        if hasattr(sender, "last_message_id"):
                            msg_id = sender.last_message_id
                        store_message(
                            selected_target_channel_id,
                            {
                                "message_id": msg_id,
                                "source_channel_id": selected_channel_id,
                                "source_message_id": selected_message_id,
                                "date": datetime.datetime.now(datetime.timezone.utc),
                                "chat_title": target_obj.get("name", ""),
                                "chat_username": "",
                                "html": message_to_send,
                            },
                        )
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
        custom_message_text=custom_message_text,
        message_option=message_option,
    )
