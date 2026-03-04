import 'dart:io';

import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';

import '../services/api_service.dart';
import '../services/voice_service.dart';

/// A conversation turn: either from the user or Trinity.
class _Turn {
  final bool  isUser;
  final String text;
  _Turn(this.isUser, this.text);
}

/// Main voice interaction screen.
///
/// Hold the mic button to record, release to send.
/// Trinity's response is played back automatically.
class VoiceScreen extends StatefulWidget {
  const VoiceScreen({super.key});

  @override
  State<VoiceScreen> createState() => _VoiceScreenState();
}

class _VoiceScreenState extends State<VoiceScreen>
    with TickerProviderStateMixin {

  final _api    = ApiService();
  final _voice  = VoiceService();
  final _scroll = ScrollController();

  final List<_Turn> _turns    = [];
  bool  _processing           = false;
  bool  _isPlayingAudio       = false;
  String? _statusMessage;           // shown in the status bar
  late AnimationController _pulseCtrl;

  @override
  void initState() {
    super.initState();
    _voice.init();
    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..repeat(reverse: true);

    _voice.playerStateStream.listen((state) {
      if (mounted) {
        setState(() {
          _isPlayingAudio =
              state.playing && state.processingState != ProcessingState.completed;
        });
      }
    });
  }

  @override
  void dispose() {
    _voice.dispose();
    _pulseCtrl.dispose();
    _scroll.dispose();
    super.dispose();
  }

  // ── Recording ─────────────────────────────────────────────────────────────

  Future<void> _onMicDown() async {
    if (_processing || _isPlayingAudio) return;

    final ok = await _voice.hasPermission();
    if (!ok) {
      _setStatus('Microphone permission denied');
      return;
    }

    await _voice.startRecording();
    setState(() => _setStatus('Listening...'));
  }

  Future<void> _onMicUp() async {
    if (!_voice.isRecording) return;

    final file = await _voice.stopRecording();
    if (file == null) {
      setState(() => _setStatus('No audio recorded'));
      return;
    }

    await _sendAudio(file);
  }

  // ── Sending ───────────────────────────────────────────────────────────────

  Future<void> _sendAudio(File file) async {
    setState(() {
      _processing = true;
      _setStatus('Thinking...');
    });

    try {
      final resp = await _api.sendVoice(file);
      _addTurns(resp);
    } on SessionExpiredException {
      if (mounted) Navigator.of(context).pushReplacementNamed('/login');
    } catch (e) {
      setState(() => _setStatus('Error: $e'));
    } finally {
      try { await file.delete(); } catch (_) {}
      setState(() => _processing = false);
    }
  }

  void _addTurns(VoiceResponse resp) {
    setState(() {
      _turns.add(_Turn(true,  resp.textInput));
      _turns.add(_Turn(false, resp.textResponse));
      _setStatus(null);
    });

    // Scroll to bottom
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });

    // Play audio response
    if (resp.audioBase64 != null) {
      _voice.playAudioBase64(resp.audioBase64!);
    } else {
      _voice.speakFallback(resp.textResponse, language: resp.language);
    }
  }

  void _setStatus(String? msg) => _statusMessage = msg;

  // ── UI ─────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;

    return Scaffold(
      backgroundColor: const Color(0xFF0A0A0F),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: const Text(
          'Trinity',
          style: TextStyle(
            color: Colors.white,
            fontSize: 20,
            fontWeight: FontWeight.w300,
            letterSpacing: 4,
          ),
        ),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.stop_circle_outlined, color: Colors.white54),
            tooltip: 'Stop playback',
            onPressed: _voice.stopPlayback,
          ),
        ],
      ),
      body: Column(
        children: [
          // ── Conversation history ─────────────────────────────────────────
          Expanded(
            child: _turns.isEmpty
                ? _emptyState()
                : ListView.builder(
                    controller: _scroll,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 8,
                    ),
                    itemCount: _turns.length,
                    itemBuilder: (_, i) => _bubble(_turns[i]),
                  ),
          ),

          // ── Status bar ───────────────────────────────────────────────────
          if (_statusMessage != null || _processing || _isPlayingAudio)
            _StatusBar(
              message:      _statusMessage,
              isProcessing: _processing,
              isPlaying:    _isPlayingAudio,
            ),

          // ── Mic button ───────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.all(32),
            child: _MicButton(
              isRecording:  _voice.isRecording,
              isDisabled:   _processing || _isPlayingAudio,
              pulseCtrl:    _pulseCtrl,
              onTapDown:    _onMicDown,
              onTapUp:      _onMicUp,
            ),
          ),
        ],
      ),
    );
  }

  Widget _emptyState() {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.mic_none, size: 64, color: Colors.white12),
          SizedBox(height: 16),
          Text(
            'Hold to speak',
            style: TextStyle(color: Colors.white24, fontSize: 16),
          ),
        ],
      ),
    );
  }

  Widget _bubble(_Turn turn) {
    final isUser  = turn.isUser;
    final bgColor = isUser
        ? const Color(0xFF1C1C2E)
        : const Color(0xFF0D2137);
    final align   = isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start;
    final radius  = isUser
        ? const BorderRadius.only(
            topLeft:     Radius.circular(18),
            topRight:    Radius.circular(18),
            bottomLeft:  Radius.circular(18),
            bottomRight: Radius.circular(4),
          )
        : const BorderRadius.only(
            topLeft:     Radius.circular(4),
            topRight:    Radius.circular(18),
            bottomLeft:  Radius.circular(18),
            bottomRight: Radius.circular(18),
          );

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        crossAxisAlignment: align,
        children: [
          Text(
            isUser ? 'You' : 'Trinity',
            style: TextStyle(
              fontSize: 11,
              color: isUser ? Colors.white38 : Colors.blueAccent.withOpacity(0.7),
              letterSpacing: 1,
            ),
          ),
          const SizedBox(height: 4),
          Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.78,
            ),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(color: bgColor, borderRadius: radius),
            child: Text(
              turn.text,
              style: const TextStyle(color: Colors.white, fontSize: 15, height: 1.4),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Sub-widgets ───────────────────────────────────────────────────────────────

class _StatusBar extends StatelessWidget {
  final String? message;
  final bool    isProcessing;
  final bool    isPlaying;

  const _StatusBar({
    this.message,
    required this.isProcessing,
    required this.isPlaying,
  });

  @override
  Widget build(BuildContext context) {
    String text = message ?? '';
    if (isProcessing && text.isEmpty) text = 'Thinking...';
    if (isPlaying    && text.isEmpty) text = 'Playing response...';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
      color: const Color(0xFF0D1117),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (isProcessing || isPlaying)
            const SizedBox(
              width: 14, height: 14,
              child: CircularProgressIndicator(
                strokeWidth: 1.5,
                color: Colors.blueAccent,
              ),
            ),
          if (isProcessing || isPlaying) const SizedBox(width: 10),
          Text(
            text,
            style: const TextStyle(
              color: Colors.white54,
              fontSize: 13,
            ),
          ),
        ],
      ),
    );
  }
}

class _MicButton extends StatelessWidget {
  final bool               isRecording;
  final bool               isDisabled;
  final AnimationController pulseCtrl;
  final VoidCallback       onTapDown;
  final VoidCallback       onTapUp;

  const _MicButton({
    required this.isRecording,
    required this.isDisabled,
    required this.pulseCtrl,
    required this.onTapDown,
    required this.onTapUp,
  });

  @override
  Widget build(BuildContext context) {
    final color = isDisabled
        ? Colors.white12
        : isRecording
            ? Colors.redAccent
            : Colors.blueAccent;

    return GestureDetector(
      onTapDown:   isDisabled ? null : (_) => onTapDown(),
      onTapUp:     isDisabled ? null : (_) => onTapUp(),
      onTapCancel: isDisabled ? null : onTapUp,
      child: AnimatedBuilder(
        animation: pulseCtrl,
        builder: (_, child) {
          final scale = isRecording
              ? 1.0 + pulseCtrl.value * 0.12
              : 1.0;
          return Transform.scale(
            scale: scale,
            child: child,
          );
        },
        child: Container(
          width:  80,
          height: 80,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: color.withOpacity(0.15),
            border: Border.all(color: color, width: 2),
            boxShadow: isRecording
                ? [BoxShadow(color: color.withOpacity(0.4), blurRadius: 24, spreadRadius: 4)]
                : [],
          ),
          child: Icon(
            isRecording ? Icons.stop : Icons.mic,
            color: color,
            size: 36,
          ),
        ),
      ),
    );
  }
}
