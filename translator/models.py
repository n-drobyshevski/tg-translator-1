from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
import asyncio

@dataclass
class ChannelConfig:
    """Configuration for a Telegram channel."""
    channel_id: int
    bot_token: str

@dataclass
class MetadataRequest:
    """Metadata fetch request for relay worker."""
    chat_id: int
    message_id: int
    file_id: Optional[str] = None
    message_entities: Optional[List[Dict[str, Any]]] = None
    response: asyncio.Future = field(
        default_factory=lambda: asyncio.get_event_loop().create_future()
    )

@dataclass
class MessageEvent:
    """Statistics log entry for a message event."""
    timestamp: str 
    event_type: str
    source_channel: str
    dest_channel: str
    source_channel_name: Optional[str]
    dest_channel_name: Optional[str]
    message_id: Optional[str]
    media_type: Optional[str]
    file_size_bytes: Optional[int]
    original_size: Optional[int]
    translated_size: Optional[int]
    translation_time: Optional[float]
    retry_count: Optional[int]
    posting_success: Optional[bool]
    api_error_code: Optional[int]
    exception_message: Optional[str]
    # Optional fields for edits, etc.
    edit_timestamp: Optional[str] = None
    previous_size: Optional[int]    = None
    new_size: Optional[int]         = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict, skipping None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}
