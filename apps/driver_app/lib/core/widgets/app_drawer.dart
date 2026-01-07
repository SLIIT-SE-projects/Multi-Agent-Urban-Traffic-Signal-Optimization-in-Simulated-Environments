import 'package:flutter/material.dart';
import '../../features/trip/presentation/screens/trip_setup_screen.dart';
import '../../features/navigation/presentation/screens/driver_dashboard.dart';
import '../../features/auth/presentation/screens/login_screen.dart';
import '../../features/trip/presentation/screens/vehicle_select_screen.dart';
import '../../features/profile/presentation/screens/profile_screen.dart';

class AppDrawer extends StatelessWidget {
  final String currentRoute;

  const AppDrawer({super.key, required this.currentRoute});

  @override
  Widget build(BuildContext context) {
    // Primary green color from theme
    final theme = Theme.of(context);
    final primaryColor = theme.primaryColor;

    return Drawer(
      elevation: 10,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.only(
          topRight: Radius.circular(30),
          bottomRight: Radius.circular(30),
        ),
      ),
      child: Column(
        children: [
          // Custom Header with Gradient and Shadow
          Container(
            padding: const EdgeInsets.fromLTRB(24, 60, 24, 24),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  primaryColor,
                  primaryColor.withOpacity(0.8),
                ],
              ),
              boxShadow: [
                BoxShadow(
                  color: primaryColor.withOpacity(0.3),
                  blurRadius: 15,
                  offset: const Offset(0, 5),
                ),
              ],
            ),
            child: Row(
              children: [
                // Profile Picture with Border
                Container(
                  padding: const EdgeInsets.all(3),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white, width: 2),
                  ),
                  child: const CircleAvatar(
                    radius: 30,
                    backgroundColor: Colors.white,
                    child: Icon(
                      Icons.person,
                      size: 35,
                      color: Colors.grey,
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                // User Info
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text(
                        'Thilan Randika',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'driver@ev.com',
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.9),
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // Menu Items
          Expanded(
            child: Container(
              color: Colors.white,
              child: ListView(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
                children: [
                  _buildDrawerItem(
                    context: context,
                    icon: Icons.home_rounded,
                    text: 'Home',
                    route: 'home',
                    onTap: () {
                      if (currentRoute == 'home') {
                        Navigator.pop(context);
                      } else {
                        Navigator.pushReplacement(
                          context,
                          MaterialPageRoute(
                              builder: (context) => const TripSetupScreen()),
                        );
                      }
                    },
                  ),
                  const SizedBox(height: 8),
                  _buildDrawerItem(
                    context: context,
                    icon: Icons.map_rounded,
                    text: 'Active Mission',
                    route: 'dashboard',
                    onTap: () {
                      if (currentRoute == 'dashboard') {
                        Navigator.pop(context);
                      } else {
                        Navigator.pushReplacement(
                          context,
                          MaterialPageRoute(
                              builder: (context) => const DriverDashboard()),
                        );
                      }
                    },
                  ),
                  const SizedBox(height: 8),
                  _buildDrawerItem(
                    context: context,
                    icon: Icons.directions_car_rounded,
                    text: 'Vehicle Selection',
                    route: 'vehicle_selection',
                    onTap: () {
                      if (currentRoute == 'vehicle_selection') {
                        Navigator.pop(context);
                      } else {
                        Navigator.pushReplacement(
                          context,
                          MaterialPageRoute(
                              builder: (context) => const VehicleSelectScreen()),
                        );
                      }
                    },
                  ),
                  const SizedBox(height: 8),
                  _buildDrawerItem(
                    context: context,
                    icon: Icons.person_rounded,
                    text: 'Profile',
                    route: 'profile',
                    onTap: () {
                      if (currentRoute == 'profile') {
                        Navigator.pop(context);
                      } else {
                        Navigator.pushReplacement(
                          context,
                          MaterialPageRoute(
                              builder: (context) => const ProfileScreen()),
                        );
                      }
                    },
                  ),
                  
                  // Divider and Logout
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 8),
                    child: Divider(color: Colors.grey[200], thickness: 1),
                  ),
                  
                  _buildDrawerItem(
                    context: context,
                    icon: Icons.logout_rounded,
                    text: 'Logout',
                    route: 'logout',
                    isLogout: true,
                    onTap: () {
                      Navigator.pushAndRemoveUntil(
                        context,
                        MaterialPageRoute(
                            builder: (context) => const LoginScreen()),
                        (route) => false,
                      );
                    },
                  ),
                ],
              ),
            ),
          ),
          
          // Footer / Version Info
          Padding(
            padding: const EdgeInsets.all(24.0),
            child: Text(
              'Version 1.0.0',
              style: TextStyle(
                color: Colors.grey[400],
                fontSize: 12,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDrawerItem({
    required BuildContext context,
    required IconData icon,
    required String text,
    required String route,
    required VoidCallback onTap,
    bool isLogout = false,
  }) {
    final isSelected = currentRoute == route;
    final theme = Theme.of(context);
    final primaryColor = theme.primaryColor;

    // Use red for logout if desired, or just standard style
    final contentColor = isLogout 
        ? Colors.red[400] 
        : (isSelected ? primaryColor : Colors.grey[600]);

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: isSelected ? primaryColor.withOpacity(0.08) : Colors.transparent,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Row(
            children: [
              Icon(
                icon,
                color: contentColor,
                size: 24,
              ),
              const SizedBox(width: 16),
              Text(
                text,
                style: TextStyle(
                  color: contentColor,
                  fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                  fontSize: 16,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
