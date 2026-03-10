import 'package:flutter/material.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/presentation/screens/login_screen.dart';

void main() {
  runApp(const EVPSDriverApp());
}

class EVPSDriverApp extends StatelessWidget {
  const EVPSDriverApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'EVPS Driver',
      theme: AppTheme.lightTheme,
      home: const LoginScreen(),
    );
  }
}
