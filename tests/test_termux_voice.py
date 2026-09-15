from unittest.mock import Mock, patch

from voice.termux import TermuxSpeechToText, TermuxTTS


def test_termux_tts_invokes_argv_without_shell():
    tts = TermuxTTS()
    result = Mock(returncode=0)
    with patch('voice.termux.shutil.which', return_value='/bin/termux-tts-speak'), patch(
        'voice.termux.subprocess.run', return_value=result
    ) as run:
        assert tts.speak('hello') is True
    args, kwargs = run.call_args
    assert args[0] == ['termux-tts-speak', 'hello']
    assert 'shell' not in kwargs or kwargs['shell'] is False


def test_termux_speech_to_text_accepts_plain_text():
    stt = TermuxSpeechToText()
    result = Mock(returncode=0, stdout='hello trinity\n', stderr='')
    with patch('voice.termux.shutil.which', return_value='/bin/termux-speech-to-text'), patch(
        'voice.termux.subprocess.run', return_value=result
    ):
        assert stt.transcribe('ignored.wav')['text'] == 'hello trinity'


def test_termux_speech_to_text_accepts_json():
    stt = TermuxSpeechToText()
    result = Mock(returncode=0, stdout='{"text":"hello"}\n', stderr='')
    with patch('voice.termux.shutil.which', return_value='/bin/termux-speech-to-text'), patch(
        'voice.termux.subprocess.run', return_value=result
    ):
        assert stt.transcribe('')['text'] == 'hello'
