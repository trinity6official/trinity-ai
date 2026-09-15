from types import SimpleNamespace

from voice.android_termux import TermuxSpeechToText, TermuxTTS


def test_termux_tts_reports_unavailable_without_command(monkeypatch):
    monkeypatch.setattr("voice.android_termux.shutil.which", lambda name: None)
    assert TermuxTTS().available() is False
    assert TermuxTTS().speak("hello") is False


def test_termux_tts_uses_argument_vector_not_shell(monkeypatch):
    monkeypatch.setattr("voice.android_termux.shutil.which", lambda name: "/bin/fake")
    calls = []
    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr("voice.android_termux.subprocess.run", fake_run)
    assert TermuxTTS().speak("hello; rm -rf /") is True
    assert calls[0][0] == ["termux-tts-speak", "hello; rm -rf /"]
    assert "shell" not in calls[0][1]


def test_termux_stt_parses_plain_text(monkeypatch):
    monkeypatch.setattr("voice.android_termux.shutil.which", lambda name: "/bin/fake")
    monkeypatch.setattr(
        "voice.android_termux.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="Hello Trinity\n", stderr=""),
    )
    result = TermuxSpeechToText().transcribe()
    assert result["text"] == "Hello Trinity"


def test_termux_stt_parses_json_text(monkeypatch):
    monkeypatch.setattr("voice.android_termux.shutil.which", lambda name: "/bin/fake")
    monkeypatch.setattr(
        "voice.android_termux.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout='{"text":"Hello Trinity"}', stderr=""),
    )
    assert TermuxSpeechToText().transcribe()["text"] == "Hello Trinity"

def test_trinity_voice_termux_provider_import_path(monkeypatch):
    monkeypatch.setenv("TRINITY_VOICE_PROVIDER", "termux")
    monkeypatch.setattr("voice.android_termux.TermuxTTS.available", lambda self: False)
    from voice.speak import TrinityVoice
    voice = TrinityVoice()
    assert voice.local_voice.tts.name == "termux-tts"
