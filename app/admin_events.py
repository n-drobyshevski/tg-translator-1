from flask import Blueprint, render_template, jsonify
from flask_login import current_user, login_required
import os, json
from translator.config import STATS_PATH, DEFAULT_STATS, STORE_PATH

admin_stats_bp = Blueprint("admin_stats_bp", __name__)

@admin_stats_bp.route("/admin/events", methods=["GET"])
@login_required
def admin_stats():
    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except Exception:
        stats = DEFAULT_STATS.copy()
    return render_template("admin_stats.html", stats=stats)

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
    # Return the last 100 events (most recent last)
    events = stats.get("messages", [])
    return jsonify({"events_last_100": events[-100:]})

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
    return jsonify(cache)
