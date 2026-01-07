import 'package:flutter/material.dart';

import '../../../../core/widgets/app_drawer.dart';

class DriverHomeScreen extends StatelessWidget {
  const DriverHomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Driver Home Screen'),
      ),
      drawer: const AppDrawer(currentRoute: 'home'),
      body: const Center(
        child: Text('Welcome to Driver Home'),
      ),
    );
  }
}
