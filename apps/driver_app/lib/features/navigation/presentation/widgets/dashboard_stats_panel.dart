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
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.15),
            blurRadius: 20,
            offset: const Offset(0, 5),
          )
        ],
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // SPEED
          _buildStatCard(
            context,
            "SPEED",
            speed.toStringAsFixed(0),
            "km/h",
            Icons.speed_rounded,
            Colors.blueAccent,
          ),
          
          _buildDivider(),

          // ETA
          _buildStatCard(
            context,
            "ETA",
            isGreenWaveActive ? "PREEMPTED" : eta.toStringAsFixed(0),
            isGreenWaveActive ? "" : "sec",
            isGreenWaveActive ? Icons.check_circle_rounded : Icons.timer_rounded,
            isGreenWaveActive ? const Color(0xFF2ECC71) : Colors.orangeAccent,
          ),

          _buildDivider(),

          // DISTANCE
          _buildStatCard(
            context,
            "DIST",
            distToTls.toStringAsFixed(0),
            "m",
            Icons.traffic_rounded,
            isGreenWaveActive ? const Color(0xFF2ECC71) : Colors.redAccent,
          ),
        ],
      ),
    );
  }

  Widget _buildDivider() {
    return Container(
      width: 1,
      height: 40,
      color: Colors.grey.shade200,
    );
  }

  Widget _buildStatCard(
    BuildContext context,
    String label,
    String value,
    String unit,
    IconData icon,
    Color color,
  ) {
    return Expanded(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                value,
                style: TextStyle(
                  fontSize: value == "PREEMPTED" || value == "CLEAR" ? 14 : 22,
                  fontWeight: FontWeight.w800,
                  color: value == "PREEMPTED" || value == "CLEAR" ? color : Colors.black87,
                ),
              ),
              if (unit.isNotEmpty) ...[
                const SizedBox(width: 2),
                Text(
                  unit,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: Colors.grey.shade600,
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: TextStyle(
              color: Colors.grey.shade500,
              fontSize: 10,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.0,
            ),
          ),
        ],
      ),
    );
  }
}
