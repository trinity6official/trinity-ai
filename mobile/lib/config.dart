/// Runtime defaults for the Trinity mobile client.
///
/// The API address can be changed inside the app and is persisted in secure
/// storage. A build-time value is still supported for managed deployments:
///
///   flutter run --dart-define=TRINITY_API_URL=https://trinity.example:8000
///
/// Plain HTTP is accepted only for loopback by default. An operator who uses
/// an encrypted VPN tunnel may explicitly opt in at build time with:
///   --dart-define=TRINITY_ALLOW_VPN_HTTP=true
class TrinityConfig {
  TrinityConfig._();

  /// Same-device Android testing defaults to Termux on localhost.
  /// When the M6 Mac mini arrives, enter the Mac HTTPS or encrypted-VPN URL on the login screen.
  static const String defaultBaseUrl = String.fromEnvironment(
    'TRINITY_API_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );

  static const bool allowTrustedVpnHttp = bool.fromEnvironment(
    'TRINITY_ALLOW_VPN_HTTP',
    defaultValue: false,
  );

  static const Duration requestTimeout = Duration(seconds: 120);
  static const Duration recordingMaxDuration = Duration(seconds: 60);

  static const String tokenStorageKey = 'trinity_jwt_v2';
  static const String baseUrlStorageKey = 'trinity_api_url_v1';
}
