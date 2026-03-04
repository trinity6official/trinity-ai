import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'screens/login_screen.dart';
import 'screens/voice_screen.dart';
import 'services/api_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Portrait only — voice assistants don't need landscape
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // Determine initial route based on stored token
  final hasToken = await ApiService().hasToken();

  runApp(TrinityApp(initialRoute: hasToken ? '/voice' : '/login'));
}

class TrinityApp extends StatelessWidget {
  final String initialRoute;

  const TrinityApp({super.key, required this.initialRoute});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Trinity',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.dark(
          primary:   Colors.blueAccent,
          surface:   const Color(0xFF0A0A0F),
          onSurface: Colors.white,
        ),
        useMaterial3: true,
        fontFamily: 'sans-serif',
      ),
      initialRoute: initialRoute,
      routes: {
        '/login': (_) => const LoginScreen(),
        '/voice': (_) => const VoiceScreen(),
      },
    );
  }
}
