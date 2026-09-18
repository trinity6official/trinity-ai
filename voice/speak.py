"""Trinity's local speech facade."""
from __future__ import annotations

from datetime import datetime
import os

from voice.local import LocalVoiceService


class TrinityVoice:
    """Local Tamil/English speech wrapper used by the Trinity composition root."""

    def __init__(self, local_voice=None):
        if local_voice is None and os.environ.get("TRINITY_VOICE_PROVIDER", "").strip().lower() == "termux":
            from voice.termux import TermuxSpeechToText, TermuxTTS
            local_voice = LocalVoiceService(tts=TermuxTTS(), stt=TermuxSpeechToText())
        self.local_voice = local_voice or LocalVoiceService()
        self.hardware_mode = self.local_voice.can_speak()
        if self.hardware_mode:
            print("Trinity Voice: local speech provider ready")
        else:
            print("Trinity Voice: local speech unavailable - text-only mode")

    def check_hardware(self):
        """Refresh and return local speech availability."""
        self.hardware_mode = self.local_voice.can_speak()
        return self.hardware_mode

    def listen(self, audio_file):
        """Convert speech to text using the configured local STT provider."""
        try:
            return self.local_voice.listen(audio_file)
        except Exception as exc:
            print(f"Listen error: {exc}")
            return None

    def speak(self, text, language="english"):
        """Speak locally when a TTS provider is available."""
        try:
            return bool(self.local_voice.speak(text, language))
        except Exception as exc:
            print(f"Speak error: {exc}")
            return False

    def render(self, text, language="english"):
        """Render local speech bytes for an authenticated API/mobile client."""
        try:
            return self.local_voice.render(text, language)
        except Exception as exc:
            print(f"Voice render error: {exc}")
            return None

    def speak_morning_briefing(self, briefing_text, language="english"):
        print(f"Speaking morning briefing in {language}")
        return self.speak(briefing_text, language)

    def speak_alert(self, alert_text, language="english"):
        if language == "tamil":
            message = f"முக்கியமான அறிவிப்பு. {alert_text}"
        else:
            message = f"Important alert. {alert_text}"
        return self.speak(message, language)

    def speak_good_morning(self, language="english"):
        hour = datetime.now().hour
        if language == "tamil":
            if 5 <= hour < 12:
                text = "காலை வணக்கம் David. நான் Trinity. உங்கள் நிறுவனம் இன்றும் நன்றாக இருக்கிறது."
            else:
                text = "வணக்கம் David. நான் Trinity. உங்களுக்காக காத்திருந்தேன்."
        else:
            if 5 <= hour < 12:
                text = "Good morning David. I am Trinity. Your company is doing well today."
            else:
                text = "Hello David. I am Trinity. I have been watching over Trinity6 for you."
        return self.speak(text, language)
