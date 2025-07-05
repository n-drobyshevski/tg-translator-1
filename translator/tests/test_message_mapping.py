import pytest
import json
import os
from pathlib import Path
from translator.config import Config

def test_get_destination_msg_id(tmp_path):
    # Create a temporary events.json for testing
    events_data = {
        "messages": [
            {
                "source_channel_id": "12345",
                "message_id": "100",
                "dest_message_id": "200",
                "event_type": "create"
            },
            {
                "source_channel_id": "12345",
                "message_id": "100",
                "dest_message_id": "201",
                "event_type": "edit"
            }
        ]
    }
    
    events_path = tmp_path / "events.json"
    with open(events_path, "w", encoding="utf-8") as f:
        json.dump(events_data, f, indent=2)

    # Mock EVENTS_PATH in config
    original_path = os.environ.get("EVENTS_PATH")
    os.environ["EVENTS_PATH"] = str(events_path)

    try:
        config = Config()
        # Should return the most recent mapping (201)        # The function accepts integer source_channel_id and returns destination_msg_id
        result = config.get_destination_msg_id(12345, "100")
        assert result == "201", f"Expected destination_msg_id '201' but got {result}"
        # Non-existent message should return None
        assert config.get_destination_msg_id(12345, "999") is None
        # Invalid source channel should return None
        assert config.get_destination_msg_id(99999, "100") is None
        # Invalid input should raise ValueError
        with pytest.raises(ValueError):
            config.get_destination_msg_id("123", "100")  # type: ignore  # Testing invalid type
    finally:
        # Restore original EVENTS_PATH
        if original_path:
            os.environ["EVENTS_PATH"] = original_path
        else:
            del os.environ["EVENTS_PATH"]

def test_get_destination_msg_id_missing_file(tmp_path):
    # Test with non-existent events file
    events_path = tmp_path / "nonexistent.json"
    original_path = os.environ.get("EVENTS_PATH")
    os.environ["EVENTS_PATH"] = str(events_path)

    try:
        config = Config()
        assert config.get_destination_msg_id(12345, "100") is None
    finally:
        if original_path:
            os.environ["EVENTS_PATH"] = original_path
        else:
            del os.environ["EVENTS_PATH"]
