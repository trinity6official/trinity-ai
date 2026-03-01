"""
Tests for voice/language.py — LanguageDetector

LanguageDetector is pure logic with zero external dependencies — the
easiest module to test exhaustively. It determines whether David
spoke in Tamil or English, which affects every response Trinity sends.
A false detection means David receives answers in the wrong language.
"""
import pytest
from voice.language import LanguageDetector


@pytest.fixture
def detector():
    return LanguageDetector()


# ── detect ────────────────────────────────────────────────────────


class TestDetect:
    def test_empty_string_defaults_to_english(self, detector):
        assert detector.detect("") == "english"

    def test_none_like_empty_string(self, detector):
        # The method checks `if not text` so None would also return english
        # depending on caller; test the documented empty string path
        assert detector.detect("") == "english"

    def test_plain_english_sentence(self, detector):
        assert detector.detect("Hello, how are you today?") == "english"

    def test_tamil_unicode_characters(self, detector):
        assert detector.detect("வணக்கம்") == "tamil"

    def test_mixed_english_with_tamil_unicode(self, detector):
        assert detector.detect("Hello வணக்கம் world") == "tamil"

    def test_tamil_transliterated_word_nandri(self, detector):
        assert detector.detect("nandri for your help") == "tamil"

    def test_tamil_transliterated_word_vanakkam(self, detector):
        assert detector.detect("vanakkam Trinity") == "tamil"

    def test_tamil_transliterated_case_insensitive(self, detector):
        assert detector.detect("NANDRI") == "tamil"
        assert detector.detect("Vanakkam") == "tamil"

    def test_english_with_no_tamil_keywords(self, detector):
        result = detector.detect("The server is down, please investigate.")
        assert result == "english"


# ── has_tamil_script ──────────────────────────────────────────────


class TestHasTamilScript:
    def test_true_for_tamil_unicode(self, detector):
        assert detector.has_tamil_script("வணக்கம்") is True

    def test_false_for_ascii(self, detector):
        assert detector.has_tamil_script("Hello world") is False

    def test_false_for_empty(self, detector):
        assert detector.has_tamil_script("") is False

    def test_detects_single_tamil_char_in_sentence(self, detector):
        # One Tamil character mixed in English text
        assert detector.has_tamil_script("Hello ந world") is True

    def test_boundary_code_points(self, detector):
        # U+0B80 is the start of the Tamil block
        char_at_start = chr(0x0B80)
        assert detector.has_tamil_script(char_at_start) is True
        # U+0BFF is the end
        char_at_end = chr(0x0BFF)
        assert detector.has_tamil_script(char_at_end) is True
        # U+0B7F is just before the block
        char_before = chr(0x0B7F)
        assert detector.has_tamil_script(char_before) is False


# ── has_tamil_words ───────────────────────────────────────────────


class TestHasTamilWords:
    def test_true_for_known_transliterated_word(self, detector):
        assert detector.has_tamil_words("seri da, let's go") is True

    def test_true_for_romba(self, detector):
        assert detector.has_tamil_words("romba nandri") is True

    def test_false_for_unrelated_text(self, detector):
        assert detector.has_tamil_words("completely ordinary text here") is False

    def test_case_insensitive_detection(self, detector):
        assert detector.has_tamil_words("ROMBA THANKS") is True

    def test_word_embedded_in_sentence(self, detector):
        assert detector.has_tamil_words("that was vera level work!") is True


# ── translate_status ──────────────────────────────────────────────


class TestTranslateStatus:
    def test_english_healthy(self, detector):
        assert detector.translate_status("healthy", "english") == "healthy"

    def test_english_critical(self, detector):
        result = detector.translate_status("critical", "english")
        assert "immediate action" in result

    def test_tamil_healthy(self, detector):
        result = detector.translate_status("healthy", "tamil")
        assert result == "நல்ல நிலையில் உள்ளது"

    def test_tamil_offline(self, detector):
        result = detector.translate_status("offline", "tamil")
        assert result == "இயங்கவில்லை"

    def test_unknown_status_returns_itself(self, detector):
        assert detector.translate_status("banana", "english") == "banana"

    def test_unknown_language_falls_back_to_english(self, detector):
        # French is not in the translations dict → falls back to english dict
        result = detector.translate_status("healthy", "french")
        assert result == "healthy"

    def test_all_english_statuses_covered(self, detector):
        """All defined status keys must resolve to a non-empty string."""
        expected_keys = [
            "healthy", "warning", "critical",
            "online", "offline", "complete", "pending",
        ]
        for key in expected_keys:
            result = detector.translate_status(key, "english")
            assert isinstance(result, str) and len(result) > 0, (
                f"Status '{key}' returned empty or non-string translation"
            )


# ── get_response_prefix ───────────────────────────────────────────


class TestGetResponsePrefix:
    REQUIRED_KEYS = {"thinking", "checking", "done", "alert", "good", "error"}

    def test_english_prefix_has_all_required_keys(self, detector):
        prefix = detector.get_response_prefix("english")
        assert self.REQUIRED_KEYS.issubset(prefix.keys())

    def test_tamil_prefix_has_all_required_keys(self, detector):
        prefix = detector.get_response_prefix("tamil")
        assert self.REQUIRED_KEYS.issubset(prefix.keys())

    def test_english_values_are_strings(self, detector):
        prefix = detector.get_response_prefix("english")
        for key, val in prefix.items():
            assert isinstance(val, str), f"Expected str for key '{key}'"


# ── get_greeting ──────────────────────────────────────────────────


class TestGetGreeting:
    def test_english_greeting_contains_david(self, detector):
        greeting = detector.get_greeting("english")
        assert "David" in greeting

    def test_tamil_greeting_contains_david(self, detector):
        greeting = detector.get_greeting("tamil")
        assert "David" in greeting

    def test_greeting_is_nonempty_string(self, detector):
        assert isinstance(detector.get_greeting(), str)
        assert len(detector.get_greeting()) > 0


# ── detect_and_respond ────────────────────────────────────────────


class TestDetectAndRespond:
    def test_english_message_response_keys(self, detector):
        result = detector.detect_and_respond("How is the server?")
        assert result["language"] == "english"
        assert "prefix" in result
        assert "greeting" in result

    def test_tamil_message_response_keys(self, detector):
        result = detector.detect_and_respond("vanakkam, epdi irukkeenga")
        assert result["language"] == "tamil"
        assert "prefix" in result
        assert "greeting" in result


# ── format_briefing ───────────────────────────────────────────────


class TestFormatBriefing:
    def test_english_briefing_header_present(self, detector):
        briefing = detector.format_briefing({}, "english")
        assert "Trinity6 Daily Status" in briefing

    def test_english_no_alerts_shows_all_good(self, detector):
        data = {"alerts": []}
        briefing = detector.format_briefing(data, "english")
        assert "No issues today" in briefing

    def test_english_alerts_listed(self, detector):
        data = {"alerts": ["SSL expiring soon", "Workflow failed"]}
        briefing = detector.format_briefing(data, "english")
        assert "SSL expiring soon" in briefing
        assert "Workflow failed" in briefing

    def test_english_recommendation_included(self, detector):
        data = {"alerts": [], "recommendation": "Focus on clients today."}
        briefing = detector.format_briefing(data, "english")
        assert "Focus on clients today." in briefing

    def test_tamil_briefing_header_present(self, detector):
        briefing = detector.format_briefing({}, "tamil")
        assert "Trinity6 நிலை அறிக்கை" in briefing

    def test_tamil_no_alerts_shows_tamil_text(self, detector):
        data = {"alerts": []}
        briefing = detector.format_briefing(data, "tamil")
        # "No issues today" in Tamil
        assert "பிரச்சனையும் இல்லை" in briefing
