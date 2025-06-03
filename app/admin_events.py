from flask import Blueprint, render_template, jsonify, request
from flask_login import current_user, login_required
import os, json
from translator.config import STATS_PATH, DEFAULT_STATS, STORE_PATH
from html import escape
import bleach

admin_stats_bp = Blueprint("admin_stats_bp", __name__)

def escape_json_strings(obj):
    if isinstance(obj, str):
        clean = bleach.clean(obj)            # strip/escape any HTML
        return escape(clean)                 # then HTML-escape for safety
    if isinstance(obj, list):
        return [escape_json_strings(v) for v in obj]
    if isinstance(obj, dict):
        return {k: escape_json_strings(v) for k, v in obj.items()}
    return obj

@admin_stats_bp.route("/admin/events", methods=["GET"])
@login_required
def admin_stats():
    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except Exception:
        stats = DEFAULT_STATS.copy()
    return render_template("admin_events.html", stats=stats)

@admin_stats_bp.route("/admin/events/detail", methods=["GET"])
def admin_stats_detail():
    # avoid HTML redirect on unauthorized – return JSON 401 for the JS client
    if not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except Exception:
        stats = DEFAULT_STATS.copy()
    raw = stats.get("messages", [])[-100:]
    safe = escape_json_strings(raw)
    return jsonify({"events_last_100": safe})

@admin_stats_bp.route("/admin/cache/json", methods=["GET"])
@login_required
def admin_cache_json():
    # avoid HTML redirect on unauthorized – return JSON 401 for the JS client
    if not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}
    safe = escape_json_strings(cache)
    return jsonify(safe)

@admin_stats_bp.route("/admin/events/edit", methods=["POST"])
@login_required
def edit_event():
    data = request.get_json() or {}

    # Load existing stats
    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except Exception:
        stats = DEFAULT_STATS.copy()

    # Find and replace matching event
    msgs = stats.get("messages", [])
    for idx, ev in enumerate(msgs):
        if (
            str(ev.get("source_channel")) == str(data.get("source_channel"))
            and str(ev.get("message_id")) == str(data.get("message_id"))
        ):
            msgs[idx] = data
            break
    else:
        # if not found, append to list
        msgs.append(data)

    # Persist updated stats
    stats["messages"] = msgs
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    return jsonify({"status": "ok"})
