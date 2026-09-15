import 'dart:async';

import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';

import '../services/api_service.dart';
import '../services/voice_service.dart';

class _Turn {
  final bool isUser;
  final String text;
  const _Turn(this.isUser, this.text);
}

/// Trinity Mobile v0.1 home screen: authenticated chat + optional voice input.
class VoiceScreen extends StatefulWidget {
  const VoiceScreen({super.key});

  @override
  State<VoiceScreen> createState() => _VoiceScreenState();
}

class _VoiceScreenState extends State<VoiceScreen>
    with TickerProviderStateMixin {
  final _api = ApiService();
  final _voice = VoiceService();
  final _scroll = ScrollController();
  final _text = TextEditingController();

  final List<_Turn> _turns = [];
  bool _processing = false;
  bool _isPlayingAudio = false;
  bool _connected = false;
  String _liveTranscript = '';
  String? _statusMsg;
  String _server = '';
  Timer? _statusTimer;

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
          _isPlayingAudio = state.playing &&
              state.processingState != ProcessingState.completed;
        });
      }
    });

    _refreshStatus();
    _statusTimer = Timer.periodic(
      const Duration(seconds: 15),
      (_) => _refreshStatus(silent: true),
    );
  }

  @override
  void dispose() {
    _statusTimer?.cancel();
    _voice.dispose();
    _pulseCtrl.dispose();
    _scroll.dispose();
    _text.dispose();
    super.dispose();
  }

  Future<void> _refreshStatus({bool silent = false}) async {
    try {
      final server = await _api.getBaseUrl();
      final status = await _api.status();
      if (!mounted) return;
      setState(() {
        _server = server;
        _connected = status.ready;
        if (!silent && !status.ready) _statusMsg = 'Trinity is starting...';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _connected = false;
        if (!silent) _statusMsg = 'Trinity is offline';
      });
    }
  }

  Future<void> _logout() async {
    await _api.logout();
    if (mounted) Navigator.of(context).pushReplacementNamed('/login');
  }

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
    await _sendText(transcript, speakResponse: true);
  }

  Future<void> _submitTyped() async {
    final value = _text.text.trim();
    if (value.isEmpty || _processing) return;
    _text.clear();
    await _sendText(value, speakResponse: false);
  }

  Future<void> _sendText(String text, {required bool speakResponse}) async {
    setState(() {
      _processing = true;
      _connected = true;
      _turns.add(_Turn(true, text));
      _setStatus('Thinking...');
    });
    _scrollToBottom();

    try {
      final resp = await _api.sendText(text, tts: speakResponse);
      if (!mounted) return;
      setState(() {
        _turns.add(_Turn(false, resp.textResponse));
        _connected = true;
        _setStatus(null);
      });
      _scrollToBottom();
      if (speakResponse) {
        if (resp.audioBase64 != null) {
          await _voice.playAudioBase64(resp.audioBase64!);
        } else {
          await _voice.speakFallback(
            resp.textResponse,
            language: resp.language,
          );
        }
      }
    } on SessionExpiredException {
      if (mounted) Navigator.of(context).pushReplacementNamed('/login');
    } catch (e) {
      if (mounted) {
        setState(() {
          _connected = false;
          _setStatus('Error: $e');
        });
      }
    } finally {
      if (mounted) setState(() => _processing = false);
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _setStatus(String? msg) => _statusMsg = msg;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0A0F),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0A0A0F),
        elevation: 0,
        title: Column(
          children: [
            const Text(
              'TRINITY',
              style: TextStyle(
                color: Colors.white,
                fontSize: 17,
                fontWeight: FontWeight.w200,
                letterSpacing: 6,
              ),
            ),
            const SizedBox(height: 2),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 7,
                  height: 7,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _connected ? Colors.greenAccent : Colors.redAccent,
                  ),
                ),
                const SizedBox(width: 6),
                Text(
                  _connected ? 'Connected' : 'Offline',
                  style: const TextStyle(color: Colors.white38, fontSize: 10),
                ),
              ],
            ),
          ],
        ),
        centerTitle: true,
        actions: [
          PopupMenuButton<String>(
            color: const Color(0xFF151521),
            icon: const Icon(Icons.more_vert, color: Colors.white54),
            onSelected: (value) {
              if (value == 'refresh') _refreshStatus();
              if (value == 'logout') _logout();
            },
            itemBuilder: (_) => [
              PopupMenuItem(
                enabled: false,
                child: Text(
                  _server.isEmpty ? 'Trinity' : _server,
                  style: const TextStyle(color: Colors.white38, fontSize: 11),
                ),
              ),
              const PopupMenuItem(
                value: 'refresh',
                child: Text('Refresh connection'),
              ),
              const PopupMenuItem(
                value: 'logout',
                child: Text('Logout'),
              ),
            ],
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: _turns.isEmpty && _liveTranscript.isEmpty
                  ? _emptyState()
                  : ListView.builder(
                      controller: _scroll,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                      itemCount:
                          _turns.length + (_liveTranscript.isNotEmpty ? 1 : 0),
                      itemBuilder: (_, i) {
                        if (i == _turns.length && _liveTranscript.isNotEmpty) {
                          return _ghostBubble(_liveTranscript);
                        }
                        return _bubble(_turns[i]);
                      },
                    ),
            ),
            if (_statusMsg != null || _processing || _isPlayingAudio)
              _StatusBar(
                message: _statusMsg,
                isProcessing: _processing,
                isPlaying: _isPlayingAudio,
              ),
            _composer(),
          ],
        ),
      ),
    );
  }

  Widget _composer() => Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: TextField(
                controller: _text,
                minLines: 1,
                maxLines: 5,
                textInputAction: TextInputAction.newline,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: 'Message Trinity...',
                  hintStyle: const TextStyle(color: Colors.white24),
                  filled: true,
                  fillColor: const Color(0xFF151521),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 12,
                  ),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(22),
                    borderSide: BorderSide.none,
                  ),
                ),
                onSubmitted: (_) => _submitTyped(),
              ),
            ),
            const SizedBox(width: 8),
            GestureDetector(
              onTapDown: (_) => _onMicDown(),
              onTapUp: (_) => _onMicUp(),
              onTapCancel: _onMicUp,
              child: CircleAvatar(
                radius: 23,
                backgroundColor: _voice.isListening
                    ? Colors.redAccent
                    : const Color(0xFF1C1C2E),
                child: const Icon(Icons.mic, color: Colors.white),
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filled(
              onPressed: _processing ? null : _submitTyped,
              icon: const Icon(Icons.arrow_upward),
            ),
          ],
        ),
      );

  Widget _emptyState() => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: const [
            Icon(Icons.auto_awesome, size: 56, color: Colors.white12),
            SizedBox(height: 12),
            Text(
              'Trinity is ready',
              style: TextStyle(color: Colors.white38, fontSize: 16),
            ),
            SizedBox(height: 6),
            Text(
              'Type a message or hold the mic',
              style: TextStyle(color: Colors.white24, fontSize: 13),
            ),
          ],
        ),
      );

  Widget _bubble(_Turn turn) {
    final isUser = turn.isUser;
    final bg = isUser ? const Color(0xFF1C1C2E) : const Color(0xFF0D2137);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Align(
        alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
        child: Column(
          crossAxisAlignment:
              isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
          children: [
            Text(
              isUser ? 'You' : 'Trinity',
              style: TextStyle(
                fontSize: 11,
                color: isUser ? Colors.white38 : Colors.blueAccent.shade100,
              ),
            ),
            const SizedBox(height: 3),
            Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.82,
              ),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: bg,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Text(
                turn.text,
                style: const TextStyle(color: Colors.white, height: 1.4),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _ghostBubble(String text) => Opacity(
        opacity: 0.55,
        child: _bubble(_Turn(true, text)),
      );
}

class _StatusBar extends StatelessWidget {
  final String? message;
  final bool isProcessing;
  final bool isPlaying;

  const _StatusBar({
    this.message,
    required this.isProcessing,
    required this.isPlaying,
  });

  @override
  Widget build(BuildContext context) {
    final text = message ??
        (isPlaying ? 'Speaking...' : isProcessing ? 'Thinking...' : '');
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
      color: const Color(0xFF0D1117),
      child: Row(
        children: [
          if (isProcessing || isPlaying)
            const SizedBox(
              width: 14,
              height: 14,
              child: CircularProgressIndicator(strokeWidth: 1.5),
            ),
          if (isProcessing || isPlaying) const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(color: Colors.white54, fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}
