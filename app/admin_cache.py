import os
import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from translator.config import CACHE_DIR
from app.admin_manager import get_available_channels

admin_cache_bp = Blueprint("admin_cache", __name__)

def datetimeformat(value, format='%H:%M %d/%m/%Y'):
    """Format various datetime formats to a consistent string output."""
    try:
        if isinstance(value, str) and "T" in value:
            # Parse ISO with fractional seconds and TZ offsets
            dt = datetime.fromisoformat(value)
            # Convert to UTC and drop tzinfo
            if dt.tzinfo:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt.strftime(format)
        if isinstance(value, datetime):
            return value.strftime(format)
        ts = float(value)
        return datetime.fromtimestamp(ts).strftime(format)
    except Exception as e:
        print(f"[ERROR] Failed to format datetime value: {value} - {e}")
        return str(value)

def store_message(channel_id, message_data):
    """Store a message in the channel cache."""
    cache_path = os.path.join(CACHE_DIR, "channel_cache.json")
    try:
        cache_data = {}
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
        
        channel_id = str(channel_id)
        if channel_id not in cache_data:
            cache_data[channel_id] = []
            
        # Add new message at the beginning of the list
        cache_data[channel_id].insert(0, message_data)
        
        # Keep only the last 100 messages per channel
        cache_data[channel_id] = cache_data[channel_id][:100]
        
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
        return True
    except Exception as e:
        print(f"Error storing message: {e}")
        return False

def get_message_cache():
    """Load the channel cache data for message lookup"""
    try:
        cache_path = os.path.join(CACHE_DIR, "channel_cache.json")
        if not os.path.exists(cache_path):
            return {}
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading message cache: {e}")
        return {}

@admin_cache_bp.route("/admin/cache", methods=["GET"])
@login_required
def show_cache():
    """Display the channel cache contents."""
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

    # Map channel IDs to names
    channel_id_to_name = {}
    for ch in get_available_channels():
        if ch["id"]:
            channel_id_to_name[str(ch["id"])] = ch["name"]
    
    # Add test destination channel if configured
    test_dest_id = os.getenv("TARGET_CHANNEL_ID")
    if test_dest_id and str(test_dest_id) not in channel_id_to_name:
        channel_id_to_name[str(test_dest_id)] = "Test Destination Channel"

    return render_template(
        "admin_cache_view.html",
        cache_data=cache_data,
        error=error,
        channel_id_to_name=channel_id_to_name,
        active_page="cache"
    )

@admin_cache_bp.route("/admin/cache/update", methods=["POST"])
@login_required
def update_cache():
    """
    Update the cache for a given channel and message using channel_logger.store_message.
    Expects JSON payload: { "channel_id": ..., "message": {...} }
    """
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


@admin_cache_bp.route("/admin/cache/json", methods=["GET"])
@login_required
def get_cache_json():
    """Return both available channels and message cache data"""
    message_cache = get_message_cache()
    channels = get_available_channels()
    
    return jsonify({
        "channels": channels,
        "messages": message_cache  # This is the channel_cache.json data
    })

@admin_cache_bp.route("/admin/cache/clear", methods=["POST"])
@login_required
def clear_cache():
    """Clear the entire channel cache or a specific channel's cache."""
    try:
        channel_id = request.form.get("channel_id")
        cache_path = os.path.join(CACHE_DIR, "channel_cache.json")
        
        if not os.path.exists(cache_path):
            return jsonify({"success": False, "error": "Cache file does not exist"}), 404
            
        with open(cache_path, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
            
        if channel_id:
            # Clear specific channel
            if str(channel_id) in cache_data:
                del cache_data[str(channel_id)]
                message = f"Cache cleared for channel {channel_id}"
            else:
                return jsonify({"success": False, "error": f"Channel {channel_id} not found in cache"}), 404
        else:
            # Clear all channels
            cache_data = {}
            message = "All channel caches cleared"
            
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
        return jsonify({"success": True, "message": message})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@admin_cache_bp.route("/admin/cache/delete/<msg_id>", methods=["DELETE"])
@login_required
def delete_cached_message(msg_id):
    """Delete a specific message from the cache."""
    try:
        channel_id = request.args.get("channel_id")
        if not channel_id:
            return jsonify({"success": False, "error": "Channel ID is required"}), 400
            
        cache_path = os.path.join(CACHE_DIR, "channel_cache.json")
        if not os.path.exists(cache_path):
            return jsonify({"success": False, "error": "Cache file does not exist"}), 404
            
        with open(cache_path, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
            
        channel_id = str(channel_id)
        if channel_id not in cache_data:
            return jsonify({"success": False, "error": f"Channel {channel_id} not found in cache"}), 404
            
        # Find and remove the message
        messages = cache_data[channel_id]
        for i, msg in enumerate(messages):
            if str(msg.get("id")) == str(msg_id):
                del messages[i]
                break
        else:
            return jsonify({"success": False, "error": f"Message {msg_id} not found in channel {channel_id}"}), 404
            
        # Update cache file
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
        return jsonify({"success": True, "message": f"Message {msg_id} deleted from channel {channel_id}"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
