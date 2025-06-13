import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
import logging
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
    dest_channel_name: str = None,           # Human-readable dest channel name
    source_message: str = None,              # The original message text
    translated_message: str = None,          # The translated message text
    dest_message_id: str = None,             # ID of the message in the destination channel
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
        exception_message = exception_message,                      # error snippet if failed
        source_message   = source_message,                          # original message text
        translated_message = translated_message,                    # translated message text
        dest_message_id  = dest_message_id,                         # ID of the message in the destination channel
    )
    event_data = evt.to_dict()
    stats["messages"].append(event_data)
    _save_stats(stats)

def build_event_kwargs(
    message_id: str | None,
    event_type: str,
    source_channel: str | None = None,
    dest_channel: str | None = None,
    original_size: int | None = None,
    translated_size: int | None = None,
    translation_time: float | None = None,
    posting_success: bool | None = None,
    source_channel_name: str | None = None,
    dest_channel_name: str | None = None,
    source_message: str | None = None,
    translated_message: str | None = None,
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
        "message_id": message_id,  # Unique identifier for the message
        "event_type": event_type,
        "source_channel": source_channel,
        "dest_channel": dest_channel,
        "original_size": original_size,
        "translated_size": translated_size,
        "translation_time": translation_time,
        "posting_success": posting_success,
        "source_channel_name": source_channel_name,
        "dest_channel_name": dest_channel_name,
        "source_message": source_message,
        "translated_message": translated_message,
    }
    # strip None values
    clean = {k: v for k, v in base.items() if v is not None}
    clean.update(extra_fields)
    # Ensure all required positional arguments for record_event are present (fill with defaults if missing)
    required = [
        "message_id", "event_type", "source_channel", "dest_channel", "original_size",
        "translated_size", "translation_time", "posting_success",
        "source_channel_name", "dest_channel_name", "dest_message_id"
    ]
    for key in required:
        if key not in clean:
            clean[key] = None
    return clean


class EventRecorder:
    stats: Dict[str, Any]
    payload: Dict[str, Any]

    def __init__(self) -> None:
        self._load_base()
        self.reset()

    def _load_base(self) -> None:
        try:
            with open(STATS_PATH, "r", encoding="utf-8") as f:
                self.stats = json.load(f)
        except:
            self.stats = DEFAULT_STATS.copy()
        self.stats.setdefault("messages", [])

    def prefill(self) -> None:
        """
        Fill all fields of payload with default values (0, "", or None as appropriate).
        """
        from translator.models import MessageEvent
        self.payload = {}
        for field, typ in MessageEvent.__annotations__.items():
            if typ == int:
                self.payload[field] = 0
            elif typ == float:
                self.payload[field] = False
            else:
                self.payload[field] = ""

    def reset(self) -> None:
        self.prefill()

    def set(self, **kwargs: Any) -> None:
        # Set any of the above fields
        for k, v in kwargs.items():
            if k in self.payload:
                self.payload[k] = v
            else:
                raise KeyError(f"Invalid field: {k}")

    def get(self, *fields: str) -> Any | Tuple[Any, ...]:
        """
        Get the value(s) of one or more fields from the current payload.
        If one field is given, returns its value.
        If multiple fields are given, returns a tuple of values.
        """
        if len(fields) == 1:
            return self.payload.get(fields[0])
        return tuple(self.payload.get(f) for f in fields)

    def finalize(self) -> None:
        # Derive event_type if needed
        if self.payload["event_type"] is None:
            self.payload["event_type"] = (
                "edit" if self.payload["edit_timestamp"] else "create"
            )
        # Create MessageEvent and append
        evt = MessageEvent(**self.payload)
        self.stats["messages"].append(evt.to_dict())

        # Write stats
        print(f"{STATS_PATH} ")
        os.makedirs(os.path.dirname(STATS_PATH), exist_ok=True)
        with open(STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)
        logging.info("Event recorded")
        # Optionally reset for reuse
        self.reset()

    def __str__(self) -> str:
        lines = ["EventRecorder payload:"]
        for k, v in self.payload.items():
            lines.append(f"  {k}: {v!r}")
        return "\n".join(lines)