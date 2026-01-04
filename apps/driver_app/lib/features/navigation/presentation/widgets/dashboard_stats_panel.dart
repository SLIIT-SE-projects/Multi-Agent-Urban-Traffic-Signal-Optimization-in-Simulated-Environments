import 'package:flutter/material.dart';

class DashboardStatsPanel extends StatelessWidget {
  final double speed;
  final double eta;
  final double distToTls;
  final bool isGreenWaveActive;

  const DashboardStatsPanel({
    super.key,
    required this.speed,
    required this.eta,
    required this.distToTls,
    required this.isGreenWaveActive,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.black87,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isGreenWaveActive ? Colors.greenAccent : Colors.grey,
          width: 2,
        ),
        boxShadow: [
          BoxShadow(
            color: isGreenWaveActive
                ? Colors.green.withOpacity(0.5)
                : Colors.black.withOpacity(0.5),
            blurRadius: 20,
            spreadRadius: 5,
          )
        ],
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          // SPEED
          _buildInfoColumn(
              "SPEED", "${speed.toStringAsFixed(1)} km/h", Icons.speed),
          // DIVIDER
          Container(width: 1, height: 50, color: Colors.grey),
          // ETA
          _buildInfoColumn(
              "ETA", "${eta.toStringAsFixed(1)} s", Icons.timer),
          // DIVIDER
          Container(width: 1, height: 50, color: Colors.grey),
          // DISTANCE
          _buildInfoColumn(
              "DIST", "${distToTls.toStringAsFixed(0)} m", Icons.traffic),
        ],
      ),
    );
  }

  Widget _buildInfoColumn(String label, String value, IconData icon) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, color: Colors.grey),
        const SizedBox(height: 5),
        Text(
          value,
          style: const TextStyle(
              fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white),
        ),
        Text(
          label,
          style: const TextStyle(color: Colors.grey, fontSize: 12),
        ),
      ],
    );
  }
}
