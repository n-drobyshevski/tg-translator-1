from unittest.mock import patch
import pytest
from translator.services import event_logger


# Covers handling missing edit_timestamp, event inference, None fields, etc.
@patch("translator.services.stats_logger._save_stats")
@patch("translator.services.stats_logger._load_stats", return_value={"messages": []})
def test_record_event_event_type_inference_create(mock_load, mock_save):
    event_logger.record_event(
        event_type=None,
        source_channel="A",
        dest_channel="B",
        original_size=100,
        translated_size=120,
        translation_time=1.2,
        posting_success=True,
        message_id="msgid",
        source_channel_name="src",
        dest_channel_name="dst",
    )
    out = mock_save.call_args[0][0]["messages"][-1]
    assert out["event_type"] == "create"
    assert out["posting_success"] is True


@patch("translator.services.stats_logger._save_stats")
@patch("translator.services.stats_logger._load_stats", return_value={"messages": []})
def test_record_event_handles_missing_optional(mock_load, mock_save):
    # Omit lots of fields to hit all None cases
    event_logger.record_event(
        event_type="create",
        source_channel="s",
        dest_channel="d",
        original_size=1,
        translated_size=2,
        translation_time=0.5,
        posting_success=True,
    )
    msg = mock_save.call_args[0][0]["messages"][-1]
    # None fields should not be present
    assert "api_error_code" not in msg
    assert "exception_message" not in msg


@patch("translator.services.stats_logger._save_stats")
@patch("translator.services.stats_logger._load_stats", return_value={"messages": []})
def test_record_event_event_value_override(mock_load, mock_save):
    # Pass explicit event='message_edit'
    event_logger.record_event(
        event_type="edit",
        source_channel="S",
        dest_channel="D",
        original_size=3,
        translated_size=5,
        translation_time=0.1,
        posting_success=False,
        event="message_edit",
        edit_timestamp="now",
        source_channel_name="s",
        dest_channel_name="d",
    )
    msg = mock_save.call_args[0][0]["messages"][-1]
    assert msg["event_type"] == "message_edit"


def test_build_event_kwargs_fills_missing():
    # No kwargs except event_type, all required are filled with None
    d = event_logger.build_event_kwargs(event_type="create")
    # All required positional keys should be present
    for k in [
        "source_channel",
        "dest_channel",
        "original_size",
        "translated_size",
        "translation_time",
        "posting_success",
    ]:
        assert k in d


def test_build_event_kwargs_passes_extra():
    d = event_logger.build_event_kwargs(event_type="edit", foo=123, bar="baz")
    assert d["foo"] == 123 and d["bar"] == "baz"


@patch("translator.services.stats_logger._save_stats")
@patch("translator.services.stats_logger._load_stats", return_value={"messages": []})
def test_record_event_negative_values(mock_load, mock_save):
    # Should not error on negative or zero numbers
    event_logger.record_event(
        event_type="create",
        source_channel="A",
        dest_channel="B",
        original_size=0,
        translated_size=-1,
        translation_time=0,
        posting_success=False,
        retry_count=-3,
        api_error_code=0,
        exception_message="",
    )
    msg = mock_save.call_args[0][0]["messages"][-1]
    assert msg["original_size"] == 0
    assert msg["translated_size"] == -1
    assert msg["retry_count"] == -3


@patch("translator.services.stats_logger._save_stats")
@patch("translator.services.stats_logger._load_stats", return_value={"messages": []})
def test_record_event_edits_all_fields(mock_load, mock_save):
    event_logger.record_event(
        event_type="edit",
        source_channel="a",
        dest_channel="b",
        original_size=12,
        translated_size=34,
        translation_time=2.3,
        posting_success=True,
        message_id="mid",
        media_type="doc",
        file_size_bytes=789,
        api_error_code=501,
        exception_message="bad",
        event="edit",
        edit_timestamp="2023-01-01T12:00:00Z",
        previous_size=9,
        new_size=11,
        source_channel_name="Achan",
        dest_channel_name="Bchan",
    )
    msg = mock_save.call_args[0][0]["messages"][-1]
    assert msg["event_type"] == "edit"
    assert msg["edit_timestamp"] == "2023-01-01T12:00:00Z"
    assert msg["media_type"] == "doc"
    assert msg["api_error_code"] == 501


def test_build_event_kwargs_omits_none():
    out = event_logger.build_event_kwargs(
        event_type="edit", foo=123, bar="baz", translated_size=None
    )
    # "translated_size" is required, so should be present as None, extra fields as-is
    assert out["foo"] == 123 and out["bar"] == "baz"
    assert "translated_size" in out


def test_build_event_kwargs_required_keys():
    out = event_logger.build_event_kwargs(event_type="create")
    # All required keys, even if None
    for key in [
        "event_type",
        "source_channel",
        "dest_channel",
        "original_size",
        "translated_size",
        "translation_time",
        "posting_success",
        "source_channel_name",
        "dest_channel_name",
    ]:
        assert key in out


@patch("translator.services.stats_logger._save_stats")
@patch("translator.services.stats_logger._load_stats", return_value={"messages": []})
def test_record_event_basics(mock_load, mock_save):
    record_event(
        event_type="create",
        source_channel="A",
        dest_channel="B",
        original_size=10,
        translated_size=20,
        translation_time=1.0,
        posting_success=True,
        message_id="42",
    )
    args, _ = mock_save.call_args
    msgs = args[0]["messages"]
    assert msgs[-1]["event_type"] == "create"
    assert msgs[-1]["posting_success"] is True
from unittest.mock import patch
from translator.services.event_logger import record_event


@patch("translator.services.stats_logger._save_stats")
@patch("translator.services.stats_logger._load_stats", return_value={"messages": []})
def test_record_event_edit_fields(mock_load, mock_save):
    record_event(
        event_type="edit",
        source_channel="A",
        dest_channel="B",
        original_size=10,
        translated_size=20,
        translation_time=1.0,
        posting_success=True,
        edit_timestamp="2020-01-01T00:00:00Z",
        previous_size=5,
        new_size=15,
        message_id="42",
    )
    args, _ = mock_save.call_args
    assert args[0]["messages"][-1]["edit_timestamp"] == "2020-01-01T00:00:00Z"
    assert args[0]["messages"][-1]["previous_size"] == 5


@patch("translator.services.stats_logger._save_stats")
@patch("translator.services.stats_logger._load_stats", return_value={"messages": []})
def test_record_event_optional_fields(mock_load, mock_save):
    record_event(
        event_type="create",
        source_channel="A",
        dest_channel="B",
        original_size=10,
        translated_size=20,
        translation_time=1.0,
        posting_success=False,
        api_error_code=404,
        exception_message="fail",
    )
    args, _ = mock_save.call_args
    msg = args[0]["messages"][-1]
    assert msg["api_error_code"] == 404
    assert msg["exception_message"] == "fail"


@patch("translator.services.stats_logger._save_stats")
@patch("translator.services.stats_logger._load_stats", return_value={"messages": []})
def test_record_event_all_fields(mock_load, mock_save):
    # Exercise all fields for max coverage
    event_logger.record_event(
        event_type="edit",
        source_channel="s",
        dest_channel="d",
        original_size=1,
        translated_size=2,
        translation_time=0.1,
        posting_success=False,
        message_id="id",
        media_type="text",
        retry_count=1,
        api_error_code=403,
        exception_message="fail",
        file_size_bytes=999,
        event="message_edit",
        edit_timestamp="now",
        previous_size=3,
        new_size=4,
        source_channel_name="src",
        dest_channel_name="dst",
    )
    msg = mock_save.call_args[0][0]["messages"][-1]
    assert msg["media_type"] == "text"
    assert msg["file_size_bytes"] == 999
    assert msg["event_type"] == "message_edit"
    assert msg["edit_timestamp"] == "now"
    assert msg["previous_size"] == 3
    assert msg["new_size"] == 4


@patch("translator.services.stats_logger._save_stats")
@patch("translator.services.stats_logger._load_stats", return_value={"messages": []})
def test_record_event_event_type_infers_edit_or_create(mock_load, mock_save):
    # edit_timestamp triggers event=edit
    event_logger.record_event(
        event_type=None,
        source_channel="s",
        dest_channel="d",
        original_size=1,
        translated_size=2,
        translation_time=0.1,
        posting_success=True,
        edit_timestamp="now",
        source_channel_name="src",
        dest_channel_name="dst",
    )
    msg = mock_save.call_args[0][0]["messages"][-1]
    assert msg["event_type"] == "edit"
    # No edit_timestamp triggers event=create
    event_logger.record_event(
        event_type=None,
        source_channel="s",
        dest_channel="d",
        original_size=1,
        translated_size=2,
        translation_time=0.1,
        posting_success=True,
        source_channel_name="src",
        dest_channel_name="dst",
    )
    msg2 = mock_save.call_args[0][0]["messages"][-1]
    assert msg2["event_type"] == "create"


def test_build_event_kwargs_default_fields():
    out = event_logger.build_event_kwargs(
        event_type="create",
        source_channel="x",
        dest_channel="y",
        original_size=1,
        translated_size=2,
        translation_time=3,
        posting_success=True,
        source_channel_name="src",
        dest_channel_name="dst",
    )
    assert out["event_type"] == "create"
    assert out["original_size"] == 1
    # Should fill None for missing required keys
    out2 = event_logger.build_event_kwargs(event_type="create")
    for key in [
        "source_channel",
        "dest_channel",
        "original_size",
        "translated_size",
        "translation_time",
        "posting_success",
        "source_channel_name",
        "dest_channel_name",
    ]:
        assert key in out2


def test_build_event_kwargs_extra_fields():
    out = event_logger.build_event_kwargs(event_type="edit", foo=123, bar="test")
    assert out["foo"] == 123
    assert out["bar"] == "test"
