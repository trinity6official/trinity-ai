/// Runtime defaults for the Trinity mobile client.
///
/// The API address can be changed inside the app and is persisted in secure
/// storage. A build-time value is still supported for managed deployments:
///
///   flutter run --dart-define=TRINITY_API_URL=http://192.168.1.50:8000
class TrinityConfig {
  TrinityConfig._();

  /// Same-device Android testing defaults to Termux on localhost.
  /// When the M6 Mac mini arrives, enter the Mac LAN/VPN URL on the login screen.
  static const String defaultBaseUrl = String.fromEnvironment(
    'TRINITY_API_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );

  static const Duration requestTimeout = Duration(seconds: 120);
  static const Duration recordingMaxDuration = Duration(seconds: 60);

  static const String tokenStorageKey = 'trinity_jwt_v1';
  static const String baseUrlStorageKey = 'trinity_api_url_v1';
}
