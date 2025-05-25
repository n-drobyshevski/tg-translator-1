from flask import Blueprint, render_template
import os
from flask_login import login_required

admin_bp = Blueprint("admin_bp", __name__)

@admin_bp.route("/admin", methods=["GET"])
@login_required
def admin_dashboard():
    # Show only summary info and links
    info = {
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", "")[:8] + "..." if os.getenv("TELEGRAM_BOT_TOKEN") else "",
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", "")[:8] + "..." if os.getenv("ANTHROPIC_API_KEY") else "",
        "CHRISTIANVISION_CHANNEL": os.getenv("CHRISTIANVISION_CHANNEL", ""),
        "SHALTNOTKILL_CHANNEL": os.getenv("SHALTNOTKILL_CHANNEL", ""),
    }
    return render_template("admin_dashboard.html", info=info)
