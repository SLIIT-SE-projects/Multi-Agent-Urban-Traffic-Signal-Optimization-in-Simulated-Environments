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
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF2ECC71).withOpacity(0.9),
        borderRadius: BorderRadius.circular(30),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF2ECC71).withOpacity(0.4),
            blurRadius: 15,
            spreadRadius: 2,
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            padding: const EdgeInsets.all(4),
            decoration: const BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.check, color: Color(0xFF2ECC71), size: 16),
          ),
          const SizedBox(width: 12),
          Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                "GREEN WAVE ACTIVE",
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 0.5,
                ),
              ),
              Text(
                "$activeJunctionsCount Intersections Cleared",
                style: TextStyle(
                  color: Colors.white.withOpacity(0.9),
                  fontSize: 10,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
