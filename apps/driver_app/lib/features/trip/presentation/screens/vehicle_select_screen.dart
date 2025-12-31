import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import '../../../../core/constants/app_constants.dart';
import '../../../../core/widgets/app_drawer.dart';
import '../../../../core/widgets/custom_floating_app_bar.dart';

class VehicleSelectScreen extends StatefulWidget {
  const VehicleSelectScreen({super.key});

  @override
  State<VehicleSelectScreen> createState() => _VehicleSelectScreenState();
}

class _VehicleSelectScreenState extends State<VehicleSelectScreen> {
  // Mock data for vehicles
  final List<Map<String, dynamic>> _vehicles = [
    {
      'id': 'EV_0',
      'licensePlate': 'PJ-1788',
      'type': 'Mini Ambulance',
      'description': 'Capacity: 1 Patient\nFeatures: Basic Life Support, Compact Size, High Maneuverability.',
      'status': 'Idle',
    },
    {
      'id': 'EV_1',
      'licensePlate': 'DAA-4433',
      'type': 'Standard Ambulance',
      'description': 'Capacity: 2 Patients\nFeatures: Advanced Life Support, Defibrillator, Oxygen Supply.',
      'status': 'Active',
    },
    {
      'id': 'EV_2',
      'licensePlate': 'NB-9021',
      'type': 'ICU Ambulance',
      'description': 'Capacity: 1 Critical Patient\nFeatures: ICU Ventilator, Cardiac Monitor, Infusion Pumps.',
      'status': 'Idle',
    },
    {
      'id': 'EV_3',
      'licensePlate': 'CC-1122',
      'type': 'Rapid Response',
      'description': 'Capacity: First Responder Team\nFeatures: Trauma Kits, AED, Fast Response Unit.',
      'status': 'Maintenance',
    },
  ];

  String? _selectedVehicleId;
  late final PageController _pageController;

  @override
  void initState() {
    super.initState();
    _pageController = PageController(viewportFraction: 0.85);
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _handleVehicleSelect(String vehicleId) {
    setState(() {
      _selectedVehicleId = vehicleId;
    });

    ScaffoldMessenger.of(context).clearSnackBars();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Selected vehicle: $vehicleId'),
        backgroundColor: const Color(0xFF2ECC71),
        duration: const Duration(seconds: 1),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBodyBehindAppBar: true,
      drawer: const AppDrawer(currentRoute: 'vehicle_selection'),
      body: Stack(
        children: [
          // 1. Map Background
          Positioned.fill(
            child: FlutterMap(
              options: MapOptions(
                initialCenter: AppConstants.defaultMapCenter,
                initialZoom: 15.0,
                interactionOptions: const InteractionOptions(
                  flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
                ),
              ),
              children: [
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'com.evps.app',
                ),
              ],
            ),
          ),
          
          // 2. Dark Overlay
          Positioned.fill(
            child: Container(
              color: Colors.black.withOpacity(0.6),
            ),
          ),

          // 3. Vehicle Cards PageView
          Positioned(
            left: 0,
            right: 0,
            bottom: 30, // Lifted from bottom
            height: 450, // Height of the card area
            child: PageView.builder(
              controller: _pageController,
              itemCount: _vehicles.length,
              itemBuilder: (context, index) {
                final vehicle = _vehicles[index];
                return _buildVehicleCard(vehicle);
              },
            ),
          ),

          // 4. Custom Floating App Bar
          const Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: CustomFloatingAppBar(
              title: "SELECT VEHICLE",
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVehicleCard(Map<String, dynamic> vehicle) {
    final String vehicleId = vehicle['id'];
    final String licensePlate = vehicle['licensePlate'];
    final String type = vehicle['type'];
    final String description = vehicle['description'];
    final bool isSelected = _selectedVehicleId == vehicleId;
    final primaryColor = const Color(0xFF2ECC71); // AppTheme primary

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 20), // Spacing between cards
      child: GestureDetector(
        onTap: () => _handleVehicleSelect(vehicleId),
        child: Stack(
          clipBehavior: Clip.none,
          children: [
          // Main Card Container
          Container(
            width: double.infinity,
            margin: const EdgeInsets.only(top: 40), // Make space for the icon
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.2),
                  blurRadius: 15,
                  offset: const Offset(0, 5),
                ),
              ],
              border: isSelected 
                  ? Border.all(color: primaryColor, width: 3)
                  : Border.all(color: Colors.transparent, width: 3),
            ),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(24, 60, 24, 24), // Padding for content, considering top icon
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    licensePlate, // License Plate as Title
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: Colors.orange[800], // Orange like reference
                    ),
                  ),
                  const SizedBox(height: 8),
                   Text(
                    vehicleId,
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey[500],
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    type,
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: Colors.grey[800],
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    description,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 15,
                      color: Colors.black87,
                      height: 1.4,
                    ),
                    maxLines: 5,
                    overflow: TextOverflow.ellipsis,
                  ),
                  
                  // Bottom actions / Status
                  Expanded(
                    child: Align(
                     alignment: Alignment.bottomCenter,
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                           Text(
                            vehicle['status'], 
                            style: TextStyle(
                              fontSize: 18, 
                              fontWeight: FontWeight.bold,
                              color: vehicle['status'] == 'Active' ? primaryColor : Colors.grey,
                            ),
                          ),
                          
                          // Selection Button (Checkmark)
                          InkWell(
                            onTap: () => _handleVehicleSelect(vehicleId),
                            borderRadius: BorderRadius.circular(30),
                            child: Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: isSelected ? Colors.yellow[700] : Colors.grey[200],
                                shape: BoxShape.circle,
                              ),
                              child: Icon(
                                Icons.check,
                                color: isSelected ? Colors.white : Colors.grey[400],
                                size: 24,
                              ),
                            ),
                          )
                        ],
                      ),
                    ),
                  )
                ],
              ),
            ),
          ),
          
          // Floating Icon at the top
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: Center(
              child: Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: Colors.white,
                  shape: BoxShape.circle,
                  border: Border.all(color: Colors.grey[300]!, width: 4),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.1),
                      blurRadius: 8,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Icon(
                  Icons.emergency, // Ambulance Icon
                  size: 40,
                  color: Colors.blueGrey[800],
                ),
              ),
            ),
          ),
        ],
        ),
      ),
    );
  }
}
