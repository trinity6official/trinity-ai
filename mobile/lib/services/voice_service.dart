import 'dart:convert';
import 'dart:io';

import 'package:flutter_tts/flutter_tts.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

/// Manages microphone recording, audio playback, and device TTS fallback.
class VoiceService {
  final _recorder = AudioRecorder();
  final _player   = AudioPlayer();
  final _tts      = FlutterTts();

  bool _isRecording = false;

  bool get isRecording => _isRecording;

  // ── Init & dispose ────────────────────────────────────────────────────────

  Future<void> init() async {
    await _tts.setVolume(1.0);
    await _tts.setSpeechRate(0.5);
    await _tts.setPitch(1.0);
    await _tts.setLanguage('en-US');
  }

  void dispose() {
    _recorder.dispose();
    _player.dispose();
    _tts.stop();
  }

  // ── Microphone permission ─────────────────────────────────────────────────

  Future<bool> hasPermission() => _recorder.hasPermission();

  // ── Recording ─────────────────────────────────────────────────────────────

  /// Start recording to a temp file.
  /// Audio: Opus codec, 16 kHz, mono — optimal for Google STT.
  Future<void> startRecording() async {
    assert(!_isRecording, 'Already recording');
    final dir  = await getTemporaryDirectory();
    final path = '${dir.path}/trinity_${DateTime.now().millisecondsSinceEpoch}.ogg';

    await _recorder.start(
      const RecordConfig(
        encoder:     AudioEncoder.opus,
        sampleRate:  16000,
        numChannels: 1,
        bitRate:     32000,   // 32 kbps — good quality, small file
      ),
      path: path,
    );
    _isRecording = true;
  }

  /// Stop recording and return the audio file.
  /// Returns null if recording was too short or failed.
  Future<File?> stopRecording() async {
    final path   = await _recorder.stop();
    _isRecording = false;
    if (path == null) return null;
    final file = File(path);
    // Discard recordings under 0.5 KB — almost certainly empty
    if (await file.length() < 512) {
      await file.delete();
      return null;
    }
    return file;
  }

  // ── Playback ──────────────────────────────────────────────────────────────

  /// Decode base64 MP3 audio returned by the backend and play it.
  Future<void> playAudioBase64(String base64Audio) async {
    await stopPlayback();

    final bytes = base64Decode(base64Audio);
    final dir   = await getTemporaryDirectory();
    final file  = File('${dir.path}/trinity_resp_${DateTime.now().millisecondsSinceEpoch}.mp3');
    await file.writeAsBytes(bytes);

    await _player.setFilePath(file.path);
    await _player.play();

    // Clean up the temp file once playback finishes
    _player.playerStateStream.listen((state) async {
      if (state.processingState == ProcessingState.completed) {
        try {
          await file.delete();
        } catch (_) {}
      }
    });
  }

  /// Device TTS fallback — used when backend TTS is unavailable (offline).
  Future<void> speakFallback(String text, {String language = 'english'}) async {
    await _tts.setLanguage(language == 'tamil' ? 'ta-IN' : 'en-US');
    await _tts.speak(text);
  }

  Future<void> stopPlayback() async {
    await _player.stop();
    await _tts.stop();
  }

  bool get isPlaying => _player.playing;

  Stream<PlayerState> get playerStateStream => _player.playerStateStream;
}
