import os
import json
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from datetime import datetime, timezone

admin_cache_bp = Blueprint("admin_cache_bp", __name__)

def get_available_channels():
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
    test_dest_id = os.getenv("TARGET_CHANNEL_ID")
    if test_dest_id:
        channels.append({
            "name": "Test Destination Channel",
            "id": test_dest_id,
            "is_en": True,
        })
    return channels

def datetimeformat(value, format='%H:%M %d/%m/%Y'):
    try:
        if isinstance(value, str) and "T" in value:
            # parse ISO with fractional seconds and TZ offsets
            dt = datetime.fromisoformat(value)
            # convert to UTC and drop tzinfo
            if dt.tzinfo:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt.strftime(format)
        if isinstance(value, datetime):
            return value.strftime(format)
        ts = float(value)
        return datetime.fromtimestamp(ts).strftime(format)
    except Exception:
        print(f"[ERROR] Failed to format datetime value: {value}")
        return value

@admin_cache_bp.route("/admin/cache", methods=["GET"])
@login_required
def show_cache():
    try:
        from translator.services.channel_logger import CACHE_DIR
    except ImportError:
        from channel_logger import CACHE_DIR
    cache_path = os.path.join(CACHE_DIR, "channel_cache.json")
    cache_data = {}
    error = None
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
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

@admin_cache_bp.route("/admin/cache/update", methods=["POST"])
@login_required
def update_cache():
    """
    Update the cache for a given channel and message using channel_logger.store_message.
    Expects JSON payload: { "channel_id": ..., "message": {...} }
    """
    from translator.services.channel_logger import store_message

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
