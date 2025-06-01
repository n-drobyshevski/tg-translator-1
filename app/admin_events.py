from flask import Blueprint, render_template, jsonify
from flask_login import login_required
import os, json
from translator.config import STATS_PATH, DEFAULT_STATS

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
@login_required
def admin_stats_detail():
    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except Exception:
        stats = DEFAULT_STATS.copy()
    # Return the last 100 events (most recent last)
    events = stats.get("messages", [])
    return jsonify({"events_last_100": events[-100:]})
