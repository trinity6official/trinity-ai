import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../services/api_service.dart';

/// PIN entry screen.
/// Exchanges the PIN for a JWT and navigates to the voice screen.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _api        = ApiService();
  final _controller = TextEditingController();
  bool _loading     = false;
  String? _error;

  Future<void> _submit() async {
    final pin = _controller.text.trim();
    if (pin.isEmpty) return;

    setState(() { _loading = true; _error = null; });

    try {
      final ok = await _api.login(pin);
      if (!mounted) return;
      if (ok) {
        Navigator.of(context).pushReplacementNamed('/voice');
      } else {
        setState(() { _error = 'Wrong PIN'; _loading = false; });
        _controller.clear();
      }
    } catch (e) {
      setState(() { _error = 'Cannot reach Trinity: $e'; _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0A0F),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 40),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'TRINITY',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 28,
                  letterSpacing: 10,
                  fontWeight: FontWeight.w200,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Enter your PIN',
                style: TextStyle(color: Colors.white38, fontSize: 14),
              ),
              const SizedBox(height: 40),
              TextField(
                controller:    _controller,
                obscureText:   true,
                keyboardType:  TextInputType.number,
                textAlign:     TextAlign.center,
                maxLength:     8,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 28,
                  letterSpacing: 12,
                ),
                decoration: InputDecoration(
                  counterText: '',
                  hintText:    '••••',
                  hintStyle:   const TextStyle(color: Colors.white24, letterSpacing: 12),
                  filled:      true,
                  fillColor:   const Color(0xFF1C1C2E),
                  border:      OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide:   BorderSide.none,
                  ),
                ),
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                onSubmitted: (_) => _submit(),
              ),
              if (_error != null) ...[
                const SizedBox(height: 16),
                Text(
                  _error!,
                  style: const TextStyle(color: Colors.redAccent, fontSize: 13),
                  textAlign: TextAlign.center,
                ),
              ],
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton(
                  onPressed: _loading ? null : _submit,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blueAccent,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: _loading
                      ? const SizedBox(
                          width: 20, height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text(
                          'Connect',
                          style: TextStyle(fontSize: 16, letterSpacing: 2),
                        ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
