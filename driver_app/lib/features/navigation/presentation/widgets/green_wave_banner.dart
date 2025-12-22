import 'package:flutter/material.dart';

class GreenWaveBanner extends StatelessWidget {
  final int activeJunctionsCount;

  const GreenWaveBanner({
    super.key,
    required this.activeJunctionsCount,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 20),
      decoration: BoxDecoration(
        color: Colors.greenAccent.withOpacity(0.9),
        borderRadius: BorderRadius.circular(15),
      ),
      child: Column(
        children: [
          const Icon(Icons.verified, color: Colors.black, size: 50),
          const SizedBox(height: 10),
          const Text(
            "GREEN WAVE ACTIVE",
            style: TextStyle(
              color: Colors.black,
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          Text(
            "$activeJunctionsCount Intersections Cleared",
            style: const TextStyle(
              color: Colors.black87,
              fontSize: 16,
            ),
          ),
        ],
      ),
    );
  }
}
