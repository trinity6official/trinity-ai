import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../config.dart';
import '../services/api_service.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _api = ApiService();
  final _pinController = TextEditingController();
  final _serverController = TextEditingController();

  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadServer();
  }

  Future<void> _loadServer() async {
    final value = await _api.getBaseUrl();
    if (mounted) _serverController.text = value;
  }

  @override
  void dispose() {
    _pinController.dispose();
    _serverController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final pin = _pinController.text.trim();
    final server = _serverController.text.trim();
    if (pin.isEmpty || server.isEmpty) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final reachable = await _api.isReachable(baseUrl: server);
      if (!reachable) {
        throw Exception('Trinity runtime is not ready at this address');
      }
      final ok = await _api.login(pin, baseUrl: server);
      if (!mounted) return;
      if (ok) {
        Navigator.of(context).pushReplacementNamed('/home');
      } else {
        setState(() {
          _error = 'Wrong PIN';
          _loading = false;
        });
        _pinController.clear();
      }
    } on FormatException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      if (mounted) setState(() => _error = 'Cannot connect: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0A0F),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 32),
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
                const SizedBox(height: 10),
                const Text(
                  'Private connection to your local Trinity',
                  style: TextStyle(color: Colors.white38, fontSize: 13),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 36),
                TextField(
                  controller: _serverController,
                  keyboardType: TextInputType.url,
                  autocorrect: false,
                  style: const TextStyle(color: Colors.white),
                  decoration: _inputDecoration(
                    label: 'Trinity address',
                    hint: TrinityConfig.defaultBaseUrl,
                    icon: Icons.dns_outlined,
                  ),
                ),
                const SizedBox(height: 12),
                const Text(
                  'S24 test: http://127.0.0.1:8000\nMac later: http://<mac-ip>:8000 or your VPN/TLS URL',
                  style: TextStyle(color: Colors.white30, fontSize: 11),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 22),
                TextField(
                  controller: _pinController,
                  obscureText: true,
                  keyboardType: TextInputType.number,
                  textAlign: TextAlign.center,
                  maxLength: 8,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 26,
                    letterSpacing: 10,
                  ),
                  decoration: _inputDecoration(
                    label: 'PIN',
                    hint: '••••',
                    icon: Icons.lock_outline,
                  ).copyWith(counterText: ''),
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  onSubmitted: (_) => _submit(),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 14),
                  Text(
                    _error!,
                    style: const TextStyle(color: Colors.redAccent, fontSize: 13),
                    textAlign: TextAlign.center,
                  ),
                ],
                const SizedBox(height: 22),
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton(
                    onPressed: _loading ? null : _submit,
                    child: _loading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Connect'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  InputDecoration _inputDecoration({
    required String label,
    required String hint,
    required IconData icon,
  }) =>
      InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: Colors.white38),
        hintText: hint,
        hintStyle: const TextStyle(color: Colors.white24),
        prefixIcon: Icon(icon, color: Colors.white30),
        filled: true,
        fillColor: const Color(0xFF151521),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
      );
}
