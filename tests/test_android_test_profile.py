from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.android_test import ANDROID_CONFIG, phone_readiness, prepare_android_environment
from core.ai_service import build_local_ai_from_environment


def test_android_profile_sets_only_test_overrides():
    env = {}
    prepare_android_environment(env)
    assert env['TRINITY_LOCAL_AI_CONFIG'] == str(ANDROID_CONFIG)
    assert env['TRINITY_VOICE_PROVIDER'] == 'termux'
    assert env['TRINITY_API_ENABLED'] == 'false'
    assert env['TRINITY_PRESENCE_ENABLED'] == 'false'


def test_android_yaml_builds_llama_cpp_router_without_changing_mac_default():
    stack = build_local_ai_from_environment({'TRINITY_LOCAL_AI_CONFIG': str(ANDROID_CONFIG)})
    assert stack.provider_name == 'llama_cpp'
    assert stack.base_url == 'http://127.0.0.1:8080'
    assert stack.router.configured_models('general') == ('trinity-phone',)


def test_phone_readiness_reports_model_provider():
    fake_stack = SimpleNamespace(provider_available=True, base_url='http://127.0.0.1:8080')
    with patch('core.android_test.build_local_ai_from_environment', return_value=fake_stack), patch(
        'voice.termux.TermuxTTS.available', return_value=True
    ), patch('voice.termux.TermuxSpeechToText.available', return_value=True):
        ok, details = phone_readiness({})
    assert ok is True
    assert any('local model: ready' in item for item in details)
    assert any('Android TTS: ready' in item for item in details)
