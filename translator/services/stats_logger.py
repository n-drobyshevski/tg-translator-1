import os
import json
from datetime import datetime, timezone

from translator.config import STATS_PATH, DEFAULT_STATS

from translator.models import MessageEvent

def _load_stats() -> dict:
    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_STATS.copy()

def _save_stats(stats: dict) -> None:
    os.makedirs(os.path.dirname(STATS_PATH), exist_ok=True)
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def record_event(
    event_type: str,
    source_channel: str,
    dest_channel: str,
    original_size: int,
    translated_size: int,
    translation_time: float,
    posting_success: bool,
    message_id: str = None,                  # Unique identifier for the message
    media_type: str = None,                  # "text" | "photo" | "video" | "doc"
    retry_count: int = 0,                    # Number of retries for LLM or Bot API call
    api_error_code: int = None,              # HTTP status code if posting failed
    exception_message: str = None,           # Error message if posting failed
    file_size_bytes: int = None,             # Size of media file in bytes
    event: str = None,                       # "message_edit" or other event type
    edit_timestamp: str = None,              # ISO-8601 UTC timestamp for edit events
    previous_size: int = None,               # Length before edit
    new_size: int = None,                    # Length after edit
    source_channel_name: str = None,         # Human-readable source channel name
    dest_channel_name: str = None            # Human-readable dest channel name
) -> None:
    stats = _load_stats()
    stats.setdefault("messages", [])
    # Always set event to "edit" if edit_timestamp is present, else "create"
    if event is None:
        event_val = "edit" if edit_timestamp else "create"
    else:
        event_val = event
    evt = MessageEvent(
        timestamp        = datetime.now(timezone.utc).isoformat(),  # when the event was recorded
        event_type       = event_val,                               # type of event ("edit" or "create")
        edit_timestamp   = edit_timestamp,                          # for edits: when Telegram fired the update
        source_channel   = source_channel,                          # original message channel id
        source_channel_name = source_channel_name,                  # human-readable source channel name
        dest_channel     = dest_channel,                            # translated message channel id
        dest_channel_name = dest_channel_name,                      # human-readable dest channel name
        message_id       = message_id,                              # unique message identifier
        media_type       = media_type,                              # "text" | "photo" | "video" | "doc"
        file_size_bytes  = file_size_bytes,                         # size of media file in bytes
        original_size    = original_size,                           # length of the original message
        previous_size    = previous_size,                           # length before edit
        new_size         = new_size,                                # length after edit
        translated_size  = translated_size,                         # length of the translated message
        translation_time = translation_time,                        # seconds spent translating
        retry_count      = retry_count,                             # number of retry attempts
        posting_success  = posting_success,                         # True if post succeeded
        api_error_code   = api_error_code,                          # HTTP status on failure
        exception_message = exception_message                       # error snippet if failed
    )
    event_data = evt.to_dict()
    stats["messages"].append(event_data)
    _save_stats(stats)

def build_event_kwargs(
    event_type: str,
    source_channel: str | None = None,
    dest_channel: str | None = None,
    original_size: int | None = None,
    translated_size: int | None = None,
    translation_time: float | None = None,
    posting_success: bool | None = None,
    source_channel_name: str | None = None,
    dest_channel_name: str | None = None,
    **extra_fields
) -> dict:
    """
    Helper used by bot.py to create the kwargs
    expected by record_event().

    Any key left as None will be omitted from the final dict.
    `extra_fields` lets callers attach provider-specific data
    such as prompt_tokens or error_code.
    """
    base = {
        "event_type": event_type,
        "source_channel": source_channel,
        "dest_channel": dest_channel,
        "original_size": original_size,
        "translated_size": translated_size,
        "translation_time": translation_time,
        "posting_success": posting_success,
        "source_channel_name": source_channel_name,
        "dest_channel_name": dest_channel_name,
    }
    # strip None values
    clean = {k: v for k, v in base.items() if v is not None}
    clean.update(extra_fields)
    # Ensure all required positional arguments for record_event are present (fill with defaults if missing)
    required = [
        "event_type", "source_channel", "dest_channel", "original_size",
        "translated_size", "translation_time", "posting_success",
        "source_channel_name", "dest_channel_name"
    ]
    for key in required:
        if key not in clean:
            clean[key] = None
    return clean
