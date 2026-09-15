import 'dart:convert';
import 'dart:io';

import 'package:flutter_tts/flutter_tts.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// Manages on-device STT, audio playback, and device TTS fallback.
///
/// STT strategy:
///   The phone may use its on-device speech recognizer for low-latency capture
///   and send only text to /api/ask. For fully Trinity-hosted speech, a recorder
///   can upload audio to /api/voice, which uses the Mac's local STT provider.
class VoiceService {
  final _stt    = SpeechToText();
  final _player = AudioPlayer();
  final _tts    = FlutterTts();

  bool _sttAvailable = false;

  String  _lastTranscript = '';
  bool    _isListening    = false;

  String  get lastTranscript => _lastTranscript;
  bool    get isListening    => _isListening;
  bool    get isPlaying      => _player.playing;

  Stream<PlayerState> get playerStateStream => _player.playerStateStream;

  // ── Init & dispose ────────────────────────────────────────────────────────

  Future<void> init() async {
    _sttAvailable = await _stt.initialize(
      onError: (error) => _isListening = false,
    );

    await _tts.setVolume(1.0);
    await _tts.setSpeechRate(0.5);
    await _tts.setPitch(1.0);
    await _tts.setLanguage('en-US');
  }

  void dispose() {
    _stt.cancel();
    _player.dispose();
    _tts.stop();
  }

  // ── Speech-to-Text ────────────────────────────────────────────────────────

  bool get sttAvailable => _sttAvailable;

  /// Start listening. [onPartial] fires with live transcription updates.
  Future<void> startListening({
    required void Function(String text) onPartial,
    String localeId = 'en_US',
  }) async {
    if (!_sttAvailable) return;
    _lastTranscript = '';
    _isListening    = true;

    await _stt.listen(
      onResult: (result) {
        _lastTranscript = result.recognizedWords;
        onPartial(result.recognizedWords);
        if (result.finalResult) _isListening = false;
      },
      localeId:          localeId,
      listenMode:        ListenMode.confirmation,
      cancelOnError:     true,
      partialResults:    true,
      listenFor:         const Duration(seconds: 30),
      pauseFor:          const Duration(seconds: 3),
    );
  }

  /// Stop listening and return the final transcript.
  Future<String> stopListening() async {
    await _stt.stop();
    _isListening = false;
    return _lastTranscript.trim();
  }

  Future<void> cancelListening() async {
    await _stt.cancel();
    _isListening = false;
  }

  // ── Audio playback ────────────────────────────────────────────────────────

  /// Decode base64 MP3 from backend and play it.
  Future<void> playAudioBase64(String base64Audio) async {
    await stopPlayback();
    final bytes = base64Decode(base64Audio);
    final dir   = await getTemporaryDirectory();
    final file  = File(
      '${dir.path}/trinity_resp_${DateTime.now().millisecondsSinceEpoch}.mp3',
    );
    await file.writeAsBytes(bytes);
    await _player.setFilePath(file.path);
    await _player.play();

    _player.playerStateStream.listen((state) async {
      if (state.processingState == ProcessingState.completed) {
        try { await file.delete(); } catch (_) {}
      }
    });
  }

  /// Device TTS — used when backend TTS fails or is unavailable.
  Future<void> speakFallback(String text, {String language = 'english'}) async {
    await _tts.setLanguage(language == 'tamil' ? 'ta-IN' : 'en-US');
    await _tts.speak(text);
  }

  Future<void> stopPlayback() async {
    await _player.stop();
    await _tts.stop();
  }
}
