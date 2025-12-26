import 'package:flutter/material.dart';

class DriverHomeScreen extends StatelessWidget {
  const DriverHomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Driver Home Screen'),
      ),
      body: const Center(
        child: Text('Welcome to Driver Home'),
      ),
    );
  }
}
