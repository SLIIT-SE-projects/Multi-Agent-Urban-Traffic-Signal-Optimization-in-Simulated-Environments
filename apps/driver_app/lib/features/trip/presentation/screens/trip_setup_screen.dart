import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';
import '../../../../core/widgets/app_drawer.dart';
import '../../../../core/widgets/custom_floating_app_bar.dart';
import '../../../navigation/presentation/screens/driver_dashboard.dart';
import 'location_picker_screen.dart';

class TripSetupScreen extends StatefulWidget {
  const TripSetupScreen({super.key});

  @override
  State<TripSetupScreen> createState() => _TripSetupScreenState();
}

class _TripSetupScreenState extends State<TripSetupScreen> {
  final _startLocationController = TextEditingController(text: 'Katunayake');
  final _destinationController = TextEditingController();
  String _priority = 'Critical';

  final List<String> _priorities = ['Critical', 'High', 'Standard'];

  @override
  void dispose() {
    _startLocationController.dispose();
    _destinationController.dispose();
    super.dispose();
  }

  void _startMission() {
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (context) => const DriverDashboard()),
    );
  }

  Future<void> _pickLocation(TextEditingController controller) async {
    final result = await Navigator.push<LatLng>(
      context,
      MaterialPageRoute(builder: (context) => const LocationPickerScreen()),
    );

    if (result != null) {
      setState(() {
        // Format: "Lat: 6.9271, Lng: 79.8612"
        controller.text = "Lat: ${result.latitude.toStringAsFixed(4)}, Lng: ${result.longitude.toStringAsFixed(4)}";
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final primaryColor = theme.primaryColor;

    return Scaffold(
      extendBodyBehindAppBar: true,
      drawer: const AppDrawer(currentRoute: 'home'),
      body: Stack(
        children: [
          Container(
            height: double.infinity,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Colors.white,
                  Colors.grey[50]!,
                ],
              ),
            ),
            child: SingleChildScrollView(
              padding: const EdgeInsets.only(
                top: 100, // Space for the header
                left: 24,
                right: 24,
                bottom: 24,
              ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 1. Top Section: Vehicle Summary Card
              _buildVehicleSummaryCard(theme),
              const SizedBox(height: 32),

              // 2. Form Section
              Text(
                'Mission Details',
                style: theme.textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: Colors.grey[800],
                ),
              ),
              const SizedBox(height: 24),
              
              _buildLocationField(
                controller: _startLocationController,
                label: 'Start Location',
                icon: Icons.my_location_rounded,
                isReadOnly: false, 
                suffixIcon: IconButton(
                  icon: const Icon(Icons.map_rounded),
                  color: primaryColor,
                  tooltip: 'Set location on map',
                  onPressed: () => _pickLocation(_startLocationController),
                ),
              ),
              const SizedBox(height: 16),
              
              _buildLocationField(
                controller: _destinationController,
                label: 'Destination',
                icon: Icons.location_on_outlined,
                suffixIcon: IconButton(
                  icon: const Icon(Icons.map_rounded),
                  color: primaryColor,
                  tooltip: 'Set location on map',
                  onPressed: () => _pickLocation(_destinationController),
                ),
              ),
              
              const SizedBox(height: 16),
              
              // Priority Dropdown
              Container(
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.05),
                      blurRadius: 10,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<String>(
                    value: _priority,
                    icon: Icon(Icons.keyboard_arrow_down_rounded, color: primaryColor),
                    isExpanded: true,
                    items: _priorities.map((String value) {
                      return DropdownMenuItem<String>(
                        value: value,
                        child: Row(
                          children: [
                            Icon(
                              Icons.warning_rounded,
                              color: value == 'Critical' 
                                  ? Colors.red 
                                  : (value == 'High' ? Colors.orange : Colors.green),
                              size: 20,
                            ),
                            const SizedBox(width: 12),
                            Text(
                              value,
                              style: const TextStyle(
                                fontWeight: FontWeight.w600,
                                fontSize: 16,
                              ),
                            ),
                          ],
                        ),
                      );
                    }).toList(),
                    onChanged: (newValue) {
                      setState(() {
                        _priority = newValue!;
                      });
                    },
                  ),
                ),
              ),

              const SizedBox(height: 48),

              // 3. Bottom Section: Action Button
              SizedBox(
                height: 56,
                child: ElevatedButton(
                  onPressed: _startMission,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red[600], // Red for urgency
                    foregroundColor: Colors.white,
                    elevation: 8,
                    shadowColor: Colors.red.withOpacity(0.4),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.emergency_share_rounded, size: 28),
                      SizedBox(width: 12),
                      Text(
                        'START EMERGENCY MISSION',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
          ),
          // FLOATING HEADER
          const Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: CustomFloatingAppBar(
              title: "SETUP MISSION",
              titleColor: Colors.black, // Since background is white
              showGradient: false, // Clean look on white
              showBack: true,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVehicleSummaryCard(ThemeData theme) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF2D3748), // Dark background for contrast
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.2),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.directions_car_filled_rounded,
              color: Colors.white,
              size: 32,
            ),
          ),
          const SizedBox(width: 16),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Current Vehicle',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: Colors.white.withOpacity(0.6),
                ),
              ),
              const SizedBox(height: 4),
              const Text(
                'EV_0',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1,
                ),
              ),
            ],
          ),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.greenAccent.withOpacity(0.2),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: Colors.greenAccent.withOpacity(0.5)),
            ),
            child: const Text(
              'Active',
              style: TextStyle(
                color: Colors.greenAccent,
                fontWeight: FontWeight.bold,
                fontSize: 12,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLocationField({
    required TextEditingController controller,
    required String label,
    required IconData icon,
    bool isReadOnly = false,
    Widget? suffixIcon,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.grey.withOpacity(0.08),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: TextField(
        controller: controller,
        readOnly: isReadOnly,
        style: const TextStyle(
          fontWeight: FontWeight.w600,
          fontSize: 16,
        ),
        decoration: InputDecoration(
          labelText: label,
          labelStyle: TextStyle(
            color: Colors.grey[600],
            fontWeight: FontWeight.w500,
          ),
          prefixIcon: Icon(icon, color: Colors.blueGrey[400]),
          suffixIcon: suffixIcon,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(16),
            borderSide: BorderSide.none,
          ),
          filled: true,
          fillColor: Colors.white,
          contentPadding: const EdgeInsets.all(20),
        ),
      ),
    );
  }
}
