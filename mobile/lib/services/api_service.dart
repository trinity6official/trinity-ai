import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import '../config.dart';

/// Parsed response from /api/voice or /api/ask.
class VoiceResponse {
  final String textInput;
  final String textResponse;
  final String language;

  /// Base64-encoded MP3 audio. Null when tts=false or TTS failed.
  final String? audioBase64;

  const VoiceResponse({
    required this.textInput,
    required this.textResponse,
    required this.language,
    this.audioBase64,
  });

  factory VoiceResponse.fromJson(Map<String, dynamic> j) => VoiceResponse(
        textInput:    j['text_input']    as String? ?? '',
        textResponse: j['text_response'] as String? ?? '',
        language:     j['language']      as String? ?? 'english',
        audioBase64:  j['audio_base64']  as String?,
      );
}

/// HTTP client for Trinity Voice API.
///
/// Handles:
///   - JWT storage and refresh detection
///   - Multipart audio upload
///   - Error translation to readable messages
class ApiService {
  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  // ── Token management ──────────────────────────────────────────────────────

  Future<String?> _getToken() => _storage.read(key: TrinityConfig.tokenStorageKey);

  Future<void> _saveToken(String token) =>
      _storage.write(key: TrinityConfig.tokenStorageKey, value: token);

  Future<void> deleteToken() => _storage.delete(key: TrinityConfig.tokenStorageKey);

  Future<bool> hasToken() async => (await _getToken()) != null;

  // ── Auth ──────────────────────────────────────────────────────────────────

  /// Exchange a PIN for a JWT access token.
  /// Returns true on success, false on wrong PIN.
  /// Throws on network errors.
  Future<bool> login(String pin) async {
    final uri = Uri.parse('${TrinityConfig.baseUrl}/api/auth/token');
    final resp = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'pin': pin}),
        )
        .timeout(TrinityConfig.requestTimeout);

    if (resp.statusCode == 200) {
      final token = (jsonDecode(resp.body) as Map<String, dynamic>)['access_token'] as String;
      await _saveToken(token);
      return true;
    }
    if (resp.statusCode == 401) return false;
    throw _apiError(resp);
  }

  // ── Voice pipeline ────────────────────────────────────────────────────────

  /// Upload a recorded audio file and get Trinity's voice response.
  ///
  /// [audioFile] should be OGG/Opus recorded at 16 kHz mono.
  /// Throws [SessionExpiredException] if JWT is expired.
  Future<VoiceResponse> sendVoice(File audioFile) async {
    final token = await _getToken();
    if (token == null) throw SessionExpiredException();

    final uri = Uri.parse('${TrinityConfig.baseUrl}/api/voice');
    final req  = http.MultipartRequest('POST', uri)
      ..headers['Authorization'] = 'Bearer $token'
      ..files.add(
        await http.MultipartFile.fromPath(
          'audio',
          audioFile.path,
          filename: audioFile.path.split('/').last,
        ),
      );

    final streamed = await req.send().timeout(TrinityConfig.requestTimeout);
    final resp     = await http.Response.fromStream(streamed);

    _handleAuthError(resp);
    if (resp.statusCode != 200) throw _apiError(resp);
    return VoiceResponse.fromJson(jsonDecode(resp.body) as Map<String, dynamic>);
  }

  /// Send text to Trinity and get a response (optionally with TTS audio).
  Future<VoiceResponse> sendText(String text, {bool tts = true}) async {
    final token = await _getToken();
    if (token == null) throw SessionExpiredException();

    final uri  = Uri.parse('${TrinityConfig.baseUrl}/api/ask');
    final resp = await http
        .post(
          uri,
          headers: {
            'Authorization':  'Bearer $token',
            'Content-Type':   'application/json',
          },
          body: jsonEncode({'text': text, 'tts': tts}),
        )
        .timeout(TrinityConfig.requestTimeout);

    _handleAuthError(resp);
    if (resp.statusCode != 200) throw _apiError(resp);
    return VoiceResponse.fromJson(jsonDecode(resp.body) as Map<String, dynamic>);
  }

  // ── Health check ──────────────────────────────────────────────────────────

  Future<bool> isReachable() async {
    try {
      final resp = await http
          .get(Uri.parse('${TrinityConfig.baseUrl}/api/status'))
          .timeout(const Duration(seconds: 5));
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  void _handleAuthError(http.Response resp) {
    if (resp.statusCode == 401) {
      _storage.delete(key: TrinityConfig.tokenStorageKey);
      throw SessionExpiredException();
    }
  }

  Exception _apiError(http.Response resp) {
    String detail = '';
    try {
      detail = (jsonDecode(resp.body) as Map<String, dynamic>)['detail'] as String? ?? '';
    } catch (_) {}
    return Exception('Server error ${resp.statusCode}${detail.isNotEmpty ? ": $detail" : ""}');
  }
}

class SessionExpiredException implements Exception {
  @override
  String toString() => 'Session expired — please log in again';
}
