import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';

import '../services/api_service.dart';
import '../services/voice_service.dart';

class _Turn {
  final bool   isUser;
  final String text;
  const _Turn(this.isUser, this.text);
}

/// Main voice interaction screen.
///
/// Hold mic button → on-device STT listens
/// Release → transcript sent to /api/ask → Trinity responds
/// Response MP3 plays automatically
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

  final List<_Turn> _turns  = [];
  bool   _processing        = false;
  bool   _isPlayingAudio    = false;
  String _liveTranscript    = '';   // shown while STT is running
  String? _statusMsg;

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
              state.playing &&
              state.processingState != ProcessingState.completed;
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

  // ── Recording flow ────────────────────────────────────────────────────────

  Future<void> _onMicDown() async {
    if (_processing || _isPlayingAudio) return;
    if (!_voice.sttAvailable) {
      _setStatus('Speech recognition not available on this device');
      return;
    }

    setState(() {
      _liveTranscript = '';
      _setStatus('Listening...');
    });

    await _voice.startListening(
      onPartial: (text) {
        if (mounted) setState(() => _liveTranscript = text);
      },
    );
  }

  Future<void> _onMicUp() async {
    if (!_voice.isListening && _liveTranscript.isEmpty) return;

    final transcript = await _voice.stopListening();

    setState(() {
      _liveTranscript = '';
      _setStatus(null);
    });

    if (transcript.isEmpty) {
      _setStatus('Nothing heard — try again');
      return;
    }

    await _sendText(transcript);
  }

  Future<void> _sendText(String text) async {
    setState(() {
      _processing = true;
      _setStatus('Thinking...');
    });

    try {
      final resp = await _api.sendText(text, tts: true);
      _addTurns(resp);
    } on SessionExpiredException {
      if (mounted) Navigator.of(context).pushReplacementNamed('/login');
    } catch (e) {
      setState(() => _setStatus('Error: $e'));
    } finally {
      if (mounted) setState(() => _processing = false);
    }
  }

  void _addTurns(VoiceResponse resp) {
    setState(() {
      _turns.add(_Turn(true,  resp.textInput));
      _turns.add(_Turn(false, resp.textResponse));
      _setStatus(null);
    });

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve:    Curves.easeOut,
        );
      }
    });

    if (resp.audioBase64 != null) {
      _voice.playAudioBase64(resp.audioBase64!);
    } else {
      _voice.speakFallback(resp.textResponse, language: resp.language);
    }
  }

  void _setStatus(String? msg) => _statusMsg = msg;

  // ── UI ────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0A0F),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: const Text(
          'TRINITY',
          style: TextStyle(
            color:       Colors.white,
            fontSize:    18,
            fontWeight:  FontWeight.w200,
            letterSpacing: 6,
          ),
        ),
        centerTitle: true,
        actions: [
          IconButton(
            icon:    const Icon(Icons.stop_circle_outlined, color: Colors.white38),
            tooltip: 'Stop playback',
            onPressed: _voice.stopPlayback,
          ),
        ],
      ),
      body: Column(
        children: [
          // ── Conversation ─────────────────────────────────────────────────
          Expanded(
            child: _turns.isEmpty && _liveTranscript.isEmpty
                ? _emptyState()
                : ListView.builder(
                    controller: _scroll,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 8,
                    ),
                    itemCount: _turns.length + (_liveTranscript.isNotEmpty ? 1 : 0),
                    itemBuilder: (_, i) {
                      // Show live transcript as a ghost bubble at the bottom
                      if (i == _turns.length && _liveTranscript.isNotEmpty) {
                        return _ghostBubble(_liveTranscript);
                      }
                      return _bubble(_turns[i]);
                    },
                  ),
          ),

          // ── Status bar ───────────────────────────────────────────────────
          if (_statusMsg != null || _processing || _isPlayingAudio)
            _StatusBar(
              message:      _statusMsg,
              isProcessing: _processing,
              isPlaying:    _isPlayingAudio,
            ),

          // ── Mic button ───────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.all(32),
            child: _MicButton(
              isListening: _voice.isListening,
              isDisabled:  _processing || _isPlayingAudio,
              pulseCtrl:   _pulseCtrl,
              onTapDown:   _onMicDown,
              onTapUp:     _onMicUp,
            ),
          ),
        ],
      ),
    );
  }

  Widget _emptyState() => const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.mic_none, size: 64, color: Colors.white12),
            SizedBox(height: 12),
            Text(
              'Hold to speak',
              style: TextStyle(color: Colors.white24, fontSize: 15),
            ),
          ],
        ),
      );

  Widget _bubble(_Turn turn) {
    final isUser   = turn.isUser;
    final bg       = isUser ? const Color(0xFF1C1C2E) : const Color(0xFF0D2137);
    final align    = isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start;
    final radius   = isUser
        ? const BorderRadius.only(
            topLeft: Radius.circular(18), topRight: Radius.circular(18),
            bottomLeft: Radius.circular(18), bottomRight: Radius.circular(4))
        : const BorderRadius.only(
            topLeft: Radius.circular(4), topRight: Radius.circular(18),
            bottomLeft: Radius.circular(18), bottomRight: Radius.circular(18));

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        crossAxisAlignment: align,
        children: [
          Text(
            isUser ? 'You' : 'Trinity',
            style: TextStyle(
              fontSize: 11,
              color: isUser
                  ? Colors.white38
                  : Colors.blueAccent.withOpacity(0.7),
              letterSpacing: 1,
            ),
          ),
          const SizedBox(height: 3),
          Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.78,
            ),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(color: bg, borderRadius: radius),
            child: Text(
              turn.text,
              style: const TextStyle(
                color: Colors.white, fontSize: 15, height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Faded bubble showing live STT transcript while still listening.
  Widget _ghostBubble(String text) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            const Text('You',
                style: TextStyle(fontSize: 11, color: Colors.white38,
                    letterSpacing: 1)),
            const SizedBox(height: 3),
            Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.78,
              ),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: const Color(0xFF1C1C2E).withOpacity(0.5),
                borderRadius: const BorderRadius.only(
                  topLeft:     Radius.circular(18),
                  topRight:    Radius.circular(18),
                  bottomLeft:  Radius.circular(18),
                  bottomRight: Radius.circular(4),
                ),
              ),
              child: Text(
                text,
                style: const TextStyle(
                  color: Colors.white54, fontSize: 15,
                  height: 1.4, fontStyle: FontStyle.italic,
                ),
              ),
            ),
          ],
        ),
      );
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
    final text = message ??
        (isPlaying ? 'Playing...' : isProcessing ? 'Thinking...' : '');

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
      color: const Color(0xFF0D1117),
      child: Row(
        children: [
          if (isProcessing || isPlaying)
            const SizedBox(
              width: 14, height: 14,
              child: CircularProgressIndicator(
                strokeWidth: 1.5, color: Colors.blueAccent,
              ),
            ),
          if (isProcessing || isPlaying) const SizedBox(width: 10),
          Text(text,
              style: const TextStyle(color: Colors.white54, fontSize: 13)),
        ],
      ),
    );
  }
}

class _MicButton extends StatelessWidget {
  final bool                isListening;
  final bool                isDisabled;
  final AnimationController pulseCtrl;
  final VoidCallback        onTapDown;
  final VoidCallback        onTapUp;

  const _MicButton({
    required this.isListening,
    required this.isDisabled,
    required this.pulseCtrl,
    required this.onTapDown,
    required this.onTapUp,
  });

  @override
  Widget build(BuildContext context) {
    final color = isDisabled
        ? Colors.white12
        : isListening
            ? Colors.redAccent
            : Colors.blueAccent;

    return GestureDetector(
      onTapDown:   isDisabled ? null : (_) => onTapDown(),
      onTapUp:     isDisabled ? null : (_) => onTapUp(),
      onTapCancel: isDisabled ? null : onTapUp,
      child: AnimatedBuilder(
        animation: pulseCtrl,
        builder: (_, child) => Transform.scale(
          scale: isListening ? 1.0 + pulseCtrl.value * 0.12 : 1.0,
          child: child,
        ),
        child: Container(
          width: 80, height: 80,
          decoration: BoxDecoration(
            shape:     BoxShape.circle,
            color:     color.withOpacity(0.15),
            border:    Border.all(color: color, width: 2),
            boxShadow: isListening
                ? [BoxShadow(
                    color: color.withOpacity(0.4),
                    blurRadius: 24, spreadRadius: 4)]
                : [],
          ),
          child: Icon(
            isListening ? Icons.stop : Icons.mic,
            color: color, size: 36,
          ),
        ),
      ),
    );
  }
}
