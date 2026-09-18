import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import '../config.dart';

class VoiceResponse {
  final String textInput;
  final String textResponse;
  final String language;
  final String? audioBase64;

  const VoiceResponse({
    required this.textInput,
    required this.textResponse,
    required this.language,
    this.audioBase64,
  });

  factory VoiceResponse.fromJson(Map<String, dynamic> j) => VoiceResponse(
        textInput: j['text_input'] as String? ?? '',
        textResponse: j['text_response'] as String? ?? '',
        language: j['language'] as String? ?? 'english',
        audioBase64: j['audio_base64'] as String?,
      );
}

class TrinityStatus {
  final String status;
  final String version;
  final String runtime;
  final bool runtimeBound;

  const TrinityStatus({
    required this.status,
    required this.version,
    required this.runtime,
    required this.runtimeBound,
  });

  bool get ready => status == 'ok' && runtimeBound;

  factory TrinityStatus.fromJson(Map<String, dynamic> j) => TrinityStatus(
        status: j['status'] as String? ?? 'unknown',
        version: j['version'] as String? ?? '',
        runtime: j['runtime'] as String? ?? '',
        runtimeBound: j['runtime_bound'] as bool? ?? false,
      );
}

/// Authenticated HTTP client for the single Trinity runtime.
class ApiService {
  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  Future<String?> _getToken() =>
      _storage.read(key: TrinityConfig.tokenStorageKey);

  Future<void> _saveToken(String token) =>
      _storage.write(key: TrinityConfig.tokenStorageKey, value: token);

  Future<void> deleteToken() =>
      _storage.delete(key: TrinityConfig.tokenStorageKey);

  Future<bool> hasToken() async => (await _getToken()) != null;

  Future<String> getBaseUrl() async {
    final stored = await _storage.read(key: TrinityConfig.baseUrlStorageKey);
    return stored ?? TrinityConfig.defaultBaseUrl;
  }

  Future<void> saveBaseUrl(String value) async {
    final normalized = _normalizeBaseUrl(value);
    await _storage.write(
      key: TrinityConfig.baseUrlStorageKey,
      value: normalized,
    );
  }

  Future<void> logout() async => deleteToken();

  String _normalizeBaseUrl(String raw) {
    var value = raw.trim();
    while (value.endsWith('/')) {
      value = value.substring(0, value.length - 1);
    }
    final uri = Uri.tryParse(value);
    if (uri == null || !uri.hasScheme || uri.host.isEmpty) {
      throw const FormatException('Enter a valid Trinity API URL');
    }
    if (uri.scheme != 'http' && uri.scheme != 'https') {
      throw const FormatException('Trinity API URL must use http or https');
    }
    final host = uri.host.toLowerCase();
    final loopback = host == '127.0.0.1' || host == 'localhost' || host == '::1';
    if (uri.scheme == 'http' && !loopback && !TrinityConfig.allowTrustedVpnHttp) {
      throw const FormatException(
        'Remote Trinity URLs must use HTTPS. Plain HTTP is allowed only on loopback unless this build explicitly trusts an encrypted VPN tunnel.',
      );
    }
    return value;
  }

  Future<bool> login(String pin, {String? baseUrl}) async {
    final url = _normalizeBaseUrl(baseUrl ?? await getBaseUrl());
    final uri = Uri.parse('$url/api/auth/token');
    final resp = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'pin': pin}),
        )
        .timeout(TrinityConfig.requestTimeout);

    if (resp.statusCode == 200) {
      final body = jsonDecode(resp.body) as Map<String, dynamic>;
      final token = body['access_token'] as String?;
      if (token == null || token.isEmpty) {
        throw const FormatException('Trinity returned an empty access token');
      }
      await saveBaseUrl(url);
      await _saveToken(token);
      return true;
    }
    if (resp.statusCode == 401) return false;
    throw _apiError(resp);
  }

  Future<VoiceResponse> sendVoice(File audioFile) async {
    final token = await _requireToken();
    final baseUrl = await getBaseUrl();
    final uri = Uri.parse('$baseUrl/api/voice');
    final req = http.MultipartRequest('POST', uri)
      ..headers['Authorization'] = 'Bearer $token'
      ..files.add(await http.MultipartFile.fromPath(
        'audio',
        audioFile.path,
        filename: audioFile.path.split('/').last,
      ));

    final streamed = await req.send().timeout(TrinityConfig.requestTimeout);
    final resp = await http.Response.fromStream(streamed);
    await _handleAuthError(resp);
    if (resp.statusCode != 200) throw _apiError(resp);
    return VoiceResponse.fromJson(jsonDecode(resp.body) as Map<String, dynamic>);
  }

  Future<VoiceResponse> sendText(String text, {bool tts = false}) async {
    final token = await _requireToken();
    final baseUrl = await getBaseUrl();
    final uri = Uri.parse('$baseUrl/api/ask');
    final resp = await http
        .post(
          uri,
          headers: {
            'Authorization': 'Bearer $token',
            'Content-Type': 'application/json',
          },
          body: jsonEncode({'text': text, 'tts': tts}),
        )
        .timeout(TrinityConfig.requestTimeout);

    await _handleAuthError(resp);
    if (resp.statusCode != 200) throw _apiError(resp);
    return VoiceResponse.fromJson(jsonDecode(resp.body) as Map<String, dynamic>);
  }

  Future<TrinityStatus> status({String? baseUrl}) async {
    final url = _normalizeBaseUrl(baseUrl ?? await getBaseUrl());
    final resp = await http
        .get(Uri.parse('$url/api/status'))
        .timeout(const Duration(seconds: 5));
    if (resp.statusCode != 200) throw _apiError(resp);
    return TrinityStatus.fromJson(jsonDecode(resp.body) as Map<String, dynamic>);
  }

  Future<bool> isReachable({String? baseUrl}) async {
    try {
      final s = await status(baseUrl: baseUrl);
      return s.ready;
    } catch (_) {
      return false;
    }
  }

  Future<Map<String, dynamic>> capabilities() async {
    final token = await _requireToken();
    final baseUrl = await getBaseUrl();
    final resp = await http
        .get(
          Uri.parse('$baseUrl/api/capabilities'),
          headers: {'Authorization': 'Bearer $token'},
        )
        .timeout(TrinityConfig.requestTimeout);
    await _handleAuthError(resp);
    if (resp.statusCode != 200) throw _apiError(resp);
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  Future<String> _requireToken() async {
    final token = await _getToken();
    if (token == null || token.isEmpty) throw SessionExpiredException();
    return token;
  }

  Future<void> _handleAuthError(http.Response resp) async {
    if (resp.statusCode == 401) {
      await deleteToken();
      throw SessionExpiredException();
    }
  }

  Exception _apiError(http.Response resp) {
    String detail = '';
    try {
      detail = (jsonDecode(resp.body) as Map<String, dynamic>)['detail']
              as String? ??
          '';
    } catch (_) {}
    return Exception(
      'Server error ${resp.statusCode}${detail.isNotEmpty ? ": $detail" : ""}',
    );
  }
}

class SessionExpiredException implements Exception {
  @override
  String toString() => 'Session expired — please log in again';
}
