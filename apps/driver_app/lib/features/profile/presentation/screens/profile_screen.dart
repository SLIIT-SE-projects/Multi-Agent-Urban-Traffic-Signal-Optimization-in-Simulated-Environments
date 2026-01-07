import 'package:flutter/material.dart';
import '../../../../core/widgets/app_drawer.dart';
import '../../../../core/widgets/custom_floating_app_bar.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    const primaryColor = Color(0xFF4CAF50); // Matching app's green theme

    return Scaffold(
      backgroundColor: Colors.white,
      extendBodyBehindAppBar: true,
      drawer: const AppDrawer(currentRoute: 'profile'),
      body: Stack(
        children: [
          SingleChildScrollView(
            padding: const EdgeInsets.only(top: 90), // Spacing for header
            child: Column(
              children: [
                const SizedBox(height: 30),
                // TOP SECTION: Profile Image & Name
                Center(
                  child: Column(
                    children: [
                      Container(
                        width: 120,
                        height: 120,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: primaryColor,
                            width: 4,
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.1),
                              blurRadius: 10,
                              offset: const Offset(0, 5),
                            ),
                          ],
                        ),
                        child: const CircleAvatar(
                          radius: 55,
                          backgroundColor: Colors.white,
                          child: Icon(
                            Icons.person,
                            size: 60,
                            color: Colors.grey,
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      const Text(
                        'Thilan Randika',
                        style: TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.bold,
                          color: Colors.black87,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Emergency Response Driver',
                        style: TextStyle(
                          fontSize: 16,
                          color: Colors.grey[600],
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
                
                const SizedBox(height: 40),

                // STATS GRID
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: GridView.count(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    crossAxisCount: 2,
                    crossAxisSpacing: 16,
                    mainAxisSpacing: 16,
                    childAspectRatio: 1.1,
                    children: const [
                      _StatCard(
                        label: 'Total Missions',
                        value: '42',
                        icon: Icons.local_shipping_rounded,
                      ),
                      _StatCard(
                        label: 'Green Waves',
                        value: '156',
                        icon: Icons.traffic_rounded,
                      ),
                      _StatCard(
                        label: 'Avg Speed',
                        value: '45',
                        unit: 'km/h',
                        icon: Icons.speed_rounded,
                      ),
                      _StatCard(
                        label: 'Hours Online',
                        value: '120h',
                        icon: Icons.timer_rounded,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
              ],
            ),
          ),
          
          // FLOATING HEADER
          const Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: CustomFloatingAppBar(
              title: "MY PROFILE",
              titleColor: Colors.black,
              showGradient: false,
            ),
          ),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final String? unit;
  final IconData icon;

  const _StatCard({
    required this.label,
    required this.value,
    this.unit,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    const primaryColor = Color(0xFF4CAF50);

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.grey.withOpacity(0.1),
            spreadRadius: 2,
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
        border: Border.all(color: Colors.grey.withOpacity(0.1)),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: Colors.grey[400], size: 28),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                value,
                style: const TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.bold,
                  color: primaryColor,
                ),
              ),
              if (unit != null) ...[
                const SizedBox(width: 4),
                Text(
                  unit!,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: primaryColor,
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 8),
          Text(
            label,
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey[600],
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}
