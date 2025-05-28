from flask import Blueprint, render_template
from flask_login import login_required
import os, json
from translator.stats_logger import STATS_PATH, DEFAULT_STATS

admin_stats_bp = Blueprint("admin_stats_bp", __name__)

@admin_stats_bp.route("/admin/stats", methods=["GET"])
@login_required
def admin_stats():
    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except Exception:
        stats = DEFAULT_STATS.copy()
    return render_template("admin_stats.html", stats=stats)
