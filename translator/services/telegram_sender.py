import logging
from typing import List, Optional, Tuple, Any

import requests
from dotenv import load_dotenv
from translator.config import CHANNEL_CONFIGS, BOT_TOKEN
from translator.services.event_logger import EventRecorder


load_dotenv()

_SESSION = requests.Session()


def sanitize_html(text: str) -> str:
    """Sanitize HTML for Telegram by removing or replacing unsupported tags."""
    return (
        text.replace("<p>", "")
        .replace("</p>", "")
        .replace("<br>", "\n")
        .replace("<br/>", "\n")
        .replace("<br />", "\n")
    )


def get_channel_config(target: str):
    cfg = CHANNEL_CONFIGS.get(target)
    if not cfg:
        logging.error("Unknown channel type: %s", target)
        return None, "Unknown channel type"
    if not getattr(cfg, "channel_id", None):
        logging.error("No channel_id for %s", target)
        return None, "No channel_id for target"
    return cfg, None


class TelegramSender:
    def __init__(self):
        self.configs = CHANNEL_CONFIGS
        self.MAX_MESSAGE_LENGTH = 4096

    def split_message(self, text: str) -> List[str]:
        """Split into <=4096‑char chunks, preserving lines."""
        if len(text) <= self.MAX_MESSAGE_LENGTH:
            return [text]
        messages, current = [], ""
        for line in text.split("\n"):
            if len(current) + len(line) + 1 > self.MAX_MESSAGE_LENGTH:
                messages.append(current.rstrip("\n"))
                current = line + "\n"
            else:
                current += line + "\n"
        if current:
            messages.append(current.rstrip("\n"))
        return messages

    def _extract_meta_fields(
        self, meta: Any, target: str
    ) -> Tuple[str, Optional[int], Optional[str], Optional[Any]]:
        """Extract media_type, file_size_bytes, source_channel, message_id from meta/source_msg."""
        media_type = "text"
        file_size_bytes = None
        source_channel = None
        message_id = None
        if meta is not None:
            source_msg = meta.get("source_msg")
            if source_msg:
                if hasattr(source_msg, "photo") and getattr(source_msg, "photo", None):
                    media_type = "photo"
                    file_size_bytes = getattr(source_msg.photo, "file_size", None)
                elif hasattr(source_msg, "video") and getattr(
                    source_msg, "video", None
                ):
                    media_type = "video"
                    file_size_bytes = getattr(source_msg.video, "file_size", None)
                elif hasattr(source_msg, "document") and getattr(
                    source_msg, "document", None
                ):
                    media_type = "doc"
                    file_size_bytes = getattr(source_msg.document, "file_size", None)
                if hasattr(source_msg, "chat"):
                    source_channel = str(getattr(source_msg.chat, "id", None))
                message_id = getattr(source_msg, "id", None) or getattr(
                    source_msg, "message_id", None
                )
        if not source_channel and meta is not None:
            source_channel = str(meta.get("source_channel_id", ""))
        return media_type, file_size_bytes, source_channel, message_id

    def _store_message(
        self,
        sent_chat_id: Optional[int],
        sent_msg_id: Optional[int],
        source_msg: Any,
        target: str,
        html_content: str,
        meta: Any,
    ) -> None:
        mapping = meta.get("mapping") if meta else None
        dest_channel_id = None
        if mapping:
            for k, v in mapping.items():
                if v == target:
                    dest_channel_id = k
                    break
        if dest_channel_id:
            dest_msg_data = {
                "message_id": sent_msg_id,
                "date": getattr(source_msg, "date", None) if source_msg else None,
                "chat_title": target,
                "chat_username": "",
                "html": html_content,
                "source_channel_id": (
                    getattr(source_msg.chat, "id", None) if source_msg else "None"
                ),
                "source_message_id": (
                    (
                        getattr(source_msg, "message_id", None)
                        or getattr(source_msg, "id", None)
                    )
                    if source_msg
                    else "None"
                ),
            }
            store_message(sent_chat_id, dest_msg_data)

    def _post_telegram(
        self, url: str, *, data: dict = None, json: dict = None
    ) -> Tuple[bool, Optional[requests.Response], Optional[str]]:
        """
        Send a POST request to the Telegram Bot API.

        Returns:
            (success, response, error_message)
            - success: True if status_code is 200, else False
            - response: requests.Response object if available, else None
            - error_message: error description or exception string if failed, else None
        """
        try:
            r = _SESSION.post(url, data=data, json=json, timeout=10)
            if r.status_code != 200:
                desc = None
                try:
                    desc = r.json().get("description", r.text)
                except Exception:
                    desc = r.text
                return False, r, desc
            return True, r, None
        except Exception as e:
            return False, None, str(e)

    async def send_message(
        self,
        text: str,
        recorder: EventRecorder,
    ):
        target, dest_channel_id = recorder.get("dest_channel_name", "dest_channel_id")

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        chunks = self.split_message(text)
        sent_msg_id, posting_success = None, False

        for chunk in chunks:
            sanitized_chunk = sanitize_html(chunk)
            logging.info("Send message: Sending chunk to %s (chat_id %s)…", target, dest_channel_id)
            success, r, err = self._post_telegram(
                url,
                json={
                    "chat_id": dest_channel_id,
                    "text": sanitized_chunk,
                    "parse_mode": "HTML",
                },
            )
            exception_message = None
            if not success or r is None:
                logging.error("Send message: Failed to send to %s: %s", dest_channel_id, err)
                if r is not None:
                    try:
                        exception_message = r.json().get("description", r.text)
                    except Exception:
                        exception_message = r.text
                else:
                    exception_message = str(err)
                recorder.set(
                    dest_message_id=sent_msg_id,
                    posting_success=posting_success,
                    api_error_code=err,
                    exception_message=exception_message,
                )
                logging.error(
                    "Send message: Error sending message to %s: %s",
                    dest_channel_id,
                    exception_message,
                )
                return False
            result = r.json().get("result", {})
            sent_msg_id = result.get("message_id")
            posting_success = True
            recorder.set(
                dest_message_id=sent_msg_id,
                posting_success=posting_success,
                api_error_code=None,
                exception_message=None,
            )
        logging.info(
            "Send message: Successfully sent %d chunk(s) to %s", len(chunks), target
        )

        return True

    async def send_photo_message(
        self, photo: str, caption: str, recorder: EventRecorder
    ):
        target, dest_channel_id = recorder.get("dest_channel_name", "dest_channel_id")
        cfg, err = get_channel_config(target)
        if not cfg:
            return False, None, None, err
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        sanitized_caption = sanitize_html(caption)

        sent_msg_id, posting_success = None, False

        logging.info("Sending photo to %s (chat_id %s)…", target, cfg.channel_id)
        success, r, err = self._post_telegram(
            url,
            data={
                "chat_id": dest_channel_id,
                "photo": photo,
                "caption": sanitized_caption,
                "parse_mode": "HTML",
            },
        )
        if not success or r is None:
            logging.error("Failed to send photo to %s: %s", dest_channel_id, err)
            recorder.set(
                dest_message_id=sent_msg_id,
                posting_success=posting_success,
            )
            return False 

        result = r.json().get("result", {})
        sent_msg_id = result.get("message_id")
        posting_success = True

        recorder.set(dest_message_id=sent_msg_id)
        recorder.set(posting_success=posting_success)
        logging.info("Successfully sent photo to %s", target)
        return True

    async def edit_message(self, channel_id, message_id, text, recorder: EventRecorder):
        """
        Edit a message in a Telegram channel by channel_id and message_id.
        Returns (posting_success, api_error_code, exception_message).
        """
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
        sanitized_text = sanitize_html(text)
        payload = {
            "chat_id": channel_id,
            "message_id": message_id,
            "text": sanitized_text,
            "parse_mode": "HTML",
        }
        posting_success = False
        api_error_code = None
        exception_message = None
        sent_msg_id = None

        success, resp, err = self._post_telegram(url, data=payload)
        if not success or resp is None:
            logging.error(
                "Failed to edit message %s in %s: %s",
                message_id,
                channel_id,
                err,
            )
            api_error_code = resp.status_code if resp else None
            exception_message = err
        else:
            result = resp.json().get("result", {})
            sent_msg_id = result.get("message_id")
            posting_success = True

        recorder.set(
            dest_message_id=sent_msg_id,
            posting_success=posting_success,
            api_error_code=api_error_code,
            exception_message=exception_message,
        )
        return posting_success
