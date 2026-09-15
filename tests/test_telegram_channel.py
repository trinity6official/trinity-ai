from unittest.mock import MagicMock

from core.channels.telegram import TelegramChannel


def test_send_chunks_long_messages():
    session = MagicMock()
    channel = TelegramChannel("token", "chat", session=session)

    assert channel.send("x" * 8001) is True
    assert session.post.call_count == 3
    lengths = [len(call.kwargs["json"]["text"]) for call in session.post.call_args_list]
    assert lengths == [4000, 4000, 1]


def test_send_unconfigured_channel_is_safe():
    session = MagicMock()
    channel = TelegramChannel(None, None, session=session)

    assert channel.send("hello") is False
    session.post.assert_not_called()


def test_get_updates_passes_offset():
    session = MagicMock()
    session.get.return_value.json.return_value = {"ok": True, "result": []}
    channel = TelegramChannel("token", "chat", session=session)

    result = channel.get_updates(42)

    assert result["ok"] is True
    assert session.get.call_args.kwargs["params"]["offset"] == 42


def test_latest_offset_uses_last_update():
    session = MagicMock()
    session.get.return_value.json.return_value = {
        "ok": True,
        "result": [{"update_id": 10}, {"update_id": 20}],
    }
    channel = TelegramChannel("token", "chat", session=session)

    assert channel.latest_offset() == 21


def test_transport_errors_are_reported_without_escaping():
    session = MagicMock()
    session.post.side_effect = RuntimeError("network down")
    errors = []
    channel = TelegramChannel("token", "chat", session=session, error_handler=errors.append)

    assert channel.send("hello") is False
    assert len(errors) == 1
    assert str(errors[0]) == "network down"


def test_download_file_stays_inside_telegram_transport():
    session = MagicMock()
    metadata = MagicMock()
    metadata.json.return_value = {"ok": True, "result": {"file_path": "docs/readme.md"}}
    raw = MagicMock(); raw.content = b"hello"
    session.get.side_effect = [metadata, raw]
    channel = TelegramChannel("token", "chat", session=session)

    path, content = channel.download_file("file-1")

    assert path == "docs/readme.md"
    assert content == b"hello"
    assert session.get.call_count == 2


def test_download_file_requires_configured_remote_channel():
    channel = TelegramChannel(None, None, session=MagicMock())
    try:
        channel.download_file("file-1")
    except RuntimeError as exc:
        assert "not configured" in str(exc).lower()
    else:
        raise AssertionError("Expected unconfigured Telegram download to fail")
