from flask import Blueprint, request, render_template, session, redirect, url_for
import os
from pathlib import Path
import requests
from flask_login import login_required  # add this import

admin_bp = Blueprint("admin_bp", __name__)
TEMPLATE_PATH = Path(__file__).parent / "../translator/prompt_template.txt"


@admin_bp.route("/admin", methods=["GET", "POST"])
@login_required
def admin_dashboard():
    # Initialize configuration variables with defaults for GET or POST
    current_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    current_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    current_prompt = TEMPLATE_PATH.read_text(encoding="utf-8")
    current_cv_channel = os.getenv("CHRISTIANVISION_CHANNEL", "")
    current_cv_en_channel_id = os.getenv("CHRISTIANVISION_EN_CHANNEL_ID", "")
    current_snk_channel = os.getenv("SHALTNOTKILL_CHANNEL", "")
    current_snk_en_channel_id = os.getenv("SHALTNOTKILL_EN_CHANNEL_ID", "")
    current_target_channel_id = os.getenv("TARGET_CHANNEL_ID", "")
    current_source_test_id = os.getenv("SOURCE_TEST_ID", "")
    current_pythonanywhere_api_token = os.getenv("PYTHONANYWHERE_API_TOKEN", "")
    current_pythonanywhere_username = os.getenv("PYTHONANYWHERE_USERNAME", "")
    current_admin_password = os.getenv("ADMIN_PASSWORD", "")
    message = ""
    restart_toast = None  # added restart toast flag

    if request.method == "POST":
        action = request.form.get("action")
        if action == "load":
            current_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            current_api_key = os.getenv("ANTHROPIC_API_KEY", "")
            current_prompt = TEMPLATE_PATH.read_text(encoding="utf-8")
            current_cv_channel = os.getenv("CHRISTIANVISION_CHANNEL", "")
            current_cv_en_channel_id = os.getenv("CHRISTIANVISION_EN_CHANNEL_ID", "")
            current_snk_channel = os.getenv("SHALTNOTKILL_CHANNEL", "")
            current_snk_en_channel_id = os.getenv("SHALTNOTKILL_EN_CHANNEL_ID", "")
            current_target_channel_id = os.getenv("TARGET_CHANNEL_ID", "")
            current_source_test_id = os.getenv("SOURCE_TEST_ID", "")
            current_pythonanywhere_api_token = os.getenv("PYTHONANYWHERE_API_TOKEN", "")
            current_pythonanywhere_username = os.getenv("PYTHONANYWHERE_USERNAME", "")
            current_admin_password = os.getenv("ADMIN_PASSWORD", "")
            message = "Configuration loaded successfully."
        elif action == "restart":
            username = os.getenv("PYTHONANYWHERE_USERNAME", "")
            token = os.getenv("PYTHONANYWHERE_API_TOKEN", "")
            restart_url = "https://www.pythonanywhere.com/api/v0/user/{username}/always_on/167667/restart/".format(
                username=username
            )
            response = requests.post(
                restart_url,
                headers={"Authorization": "Token {token}".format(token=token)},
            )
            if response.status_code == 200:
                message = "PythonAnywhere Always-On task restarted successfully."
                restart_toast = True  # set toast flag for restart success
            else:
                message = (
                    "Failed to restart PythonAnywhere Always-On task: {}: {}".format(
                        response.status_code, response.content
                    )
                )
                restart_toast = False
        else:
            new_bot_token = request.form.get("bot_token")
            new_api_key = request.form.get("api_key")
            new_prompt = request.form.get("prompt_text")
            new_cv_channel = request.form.get("cv_channel")
            new_cv_en_channel_id = request.form.get("cv_en_channel_id")
            new_snk_channel = request.form.get("snk_channel")
            new_snk_en_channel_id = request.form.get("snk_en_channel_id")
            new_target_channel_id = request.form.get("target_channel_id")
            new_source_test_id = request.form.get("source_test_id")
            new_pythonanywhere_api_token = request.form.get("pythonanywhere_api_token")
            new_pythonanywhere_username = request.form.get("pythonanywhere_username")
            new_admin_password = request.form.get("admin_password")

            if new_bot_token:
                os.environ["TELEGRAM_BOT_TOKEN"] = new_bot_token
            if new_api_key:
                os.environ["ANTHROPIC_API_KEY"] = new_api_key
            if new_prompt:
                TEMPLATE_PATH.write_text(new_prompt, encoding="utf-8")
            if new_cv_channel:
                os.environ["CHRISTIANVISION_CHANNEL"] = new_cv_channel
            if new_cv_en_channel_id:
                os.environ["CHRISTIANVISION_EN_CHANNEL_ID"] = new_cv_en_channel_id
            if new_snk_channel:
                os.environ["SHALTNOTKILL_CHANNEL"] = new_snk_channel
            if new_snk_en_channel_id:
                os.environ["SHALTNOTKILL_EN_CHANNEL_ID"] = new_snk_en_channel_id
            if new_target_channel_id:
                os.environ["TARGET_CHANNEL_ID"] = new_target_channel_id
            if new_source_test_id:
                os.environ["SOURCE_TEST_ID"] = new_source_test_id
            if new_pythonanywhere_api_token:
                os.environ["PYTHONANYWHERE_API_TOKEN"] = new_pythonanywhere_api_token
            if new_pythonanywhere_username:
                os.environ["PYTHONANYWHERE_USERNAME"] = new_pythonanywhere_username
            if new_admin_password:
                os.environ["ADMIN_PASSWORD"] = new_admin_password
            message = "Configuration saved successfully."
            # Reload current values after saving
            current_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            current_api_key = os.getenv("ANTHROPIC_API_KEY", "")
            current_prompt = TEMPLATE_PATH.read_text(encoding="utf-8")
            current_cv_channel = os.getenv("CHRISTIANVISION_CHANNEL", "")
            current_cv_en_channel_id = os.getenv("CHRISTIANVISION_EN_CHANNEL_ID", "")
            current_snk_channel = os.getenv("SHALTNOTKILL_CHANNEL", "")
            current_snk_en_channel_id = os.getenv("SHALTNOTKILL_EN_CHANNEL_ID", "")
            current_target_channel_id = os.getenv("TARGET_CHANNEL_ID", "")
            current_source_test_id = os.getenv("SOURCE_TEST_ID", "")
            current_pythonanywhere_api_token = os.getenv("PYTHONANYWHERE_API_TOKEN", "")
            current_pythonanywhere_username = os.getenv("PYTHONANYWHERE_USERNAME", "")
            current_admin_password = os.getenv("ADMIN_PASSWORD", "")

    return render_template(
        "admin_dashboard.html",
        current_bot_token=current_bot_token,
        current_api_key=current_api_key,
        current_prompt=current_prompt,
        current_cv_channel=current_cv_channel,
        current_cv_en_channel_id=current_cv_en_channel_id,
        current_snk_channel=current_snk_channel,
        current_snk_en_channel_id=current_snk_en_channel_id,
        current_target_channel_id=current_target_channel_id,
        current_source_test_id=current_source_test_id,
        current_pythonanywhere_api_token=current_pythonanywhere_api_token,
        current_pythonanywhere_username=current_pythonanywhere_username,
        current_admin_password=current_admin_password,
        message=message,
        restart_toast=restart_toast,
    )
