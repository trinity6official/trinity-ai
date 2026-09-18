from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_mobile_v01_uses_real_auth_and_secure_storage():
    api = _text("mobile/lib/services/api_service.dart")
    assert "/api/auth/token" in api
    assert "FlutterSecureStorage" in api
    assert "Authorization" in api and "Bearer $token" in api
    assert "logout()" in api


def test_mobile_v01_has_runtime_server_configuration():
    config = _text("mobile/lib/config.dart")
    login = _text("mobile/lib/screens/login_screen.dart")
    api = _text("mobile/lib/services/api_service.dart")
    assert "http://127.0.0.1:8000" in config
    assert "TRINITY_ALLOW_VPN_HTTP" in config
    assert "Remote Trinity URLs must use HTTPS" in api
    assert "Trinity address" in login
    assert "saveBaseUrl" in api


def test_mobile_v01_has_chat_status_and_logout_ui():
    home = _text("mobile/lib/screens/voice_screen.dart")
    assert "Message Trinity..." in home
    assert "Connected" in home
    assert "Offline" in home
    assert "Logout" in home
    assert "_api.sendText" in home


def test_android_mobile_api_is_loopback_only_and_requires_auth():
    launcher = _text("core/android_api_test.py")
    script = _text("scripts/start_android_mobile_api.sh")
    assert 'host="127.0.0.1"' in launcher
    assert "strong salted TRINITY_APP_PIN_HASH is required" in launcher
    assert "TRINITY_JWT_SECRET must be at least 32 characters" in launcher
    assert "hash_pin" in script
    assert "sha256sum" not in script
    assert "secrets.token_hex(32)" in script
    assert "pip install --upgrade pip" not in script


def test_mobile_build_bootstraps_missing_flutter_android_scaffold():
    script = _text("mobile/prepare_android.sh")
    workflow = _text(".github/workflows/build_apk.yml")
    assert "flutter create --platforms=android --org com.trinity6 ." in script
    assert "cp \"$tmp_manifest\" \"$manifest\"" in script
    assert "./prepare_android.sh" in workflow
    assert "trinity-mobile-apk" in workflow
