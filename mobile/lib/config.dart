/// Runtime configuration.
///
/// Override [baseUrl] at build time:
///   flutter run --dart-define=TRINITY_API_URL=https://trinity.example.com
///
/// Generate [pinHash] with:
///   echo -n "YOUR_PIN" | sha256sum
///   Then set TRINITY_APP_PIN_HASH env var on the server with that value.
class TrinityConfig {
  TrinityConfig._();

  /// Backend URL.
  /// Android emulator → host machine:  http://10.0.2.2:8000
  /// Physical device on same Wi-Fi:    http://192.168.x.x:8000
  /// Production:                        https://trinity.yourdomain.com
  static const String baseUrl = String.fromEnvironment(
    'TRINITY_API_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  static const Duration requestTimeout   = Duration(seconds: 45);
  static const Duration recordingMaxDuration = Duration(seconds: 60);

  /// Key used to store the JWT in secure storage.
  static const String tokenStorageKey = 'trinity_jwt_v1';
}
