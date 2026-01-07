import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import '../../data/models/vehicle_status.dart';
import '../../data/services/websocket_service.dart';
import '../widgets/dashboard_stats_panel.dart';
import '../widgets/green_wave_banner.dart';
import '../widgets/live_map.dart';
import '../../../../core/constants/app_constants.dart';

import '../../../../core/widgets/app_drawer.dart';
import '../../../../core/widgets/custom_floating_app_bar.dart';

class DriverDashboard extends StatefulWidget {
  const DriverDashboard({super.key});

  @override
  State<DriverDashboard> createState() => _DriverDashboardState();
}

class _DriverDashboardState extends State<DriverDashboard> {
  late WebSocketService _webSocketService;
  final MapController _mapController = MapController();

  // App State
  String currentEvId = AppConstants.defaultEvId;
  VehicleStatus _status = VehicleStatus.empty();
  bool hasData = false;

  @override
  void initState() {
    super.initState();
    _webSocketService = WebSocketService();
  }

  @override
  void dispose() {
    _webSocketService.dispose();
    super.dispose();
  }

  void _switchVehicle(String newId) {
    setState(() {
      currentEvId = newId;
      _webSocketService.switchVehicle(newId);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBodyBehindAppBar: true,
      drawer: const AppDrawer(currentRoute: 'dashboard'),
      body: StreamBuilder<VehicleStatus>(
        stream: _webSocketService.vehicleStatusStream,
        builder: (context, snapshot) {
          if (snapshot.hasData) {
            _status = snapshot.data!;
            if (_status.position.latitude != 0 &&
                _status.position.longitude != 0) {
              hasData = true;
              try {
                _mapController.move(_status.position, 16.0);
              } catch (e) {
                // Controller might not be ready
              }
            }
          }

          return Stack(
            children: [
              // 1. FULL SCREEN MAP
              Positioned.fill(
                child: LiveMap(
                  mapController: _mapController,
                  evPosition: _status.position,
                  activeJunctions: _status.activeJunctions,
                  hasData: hasData,
                ),
              ),

              // 2. CUSTOM TOP BAR (Menu + Title + Vehicle Selector)
              Positioned(
                top: 0,
                left: 0,
                right: 0,
                child: CustomFloatingAppBar(
                  title: "ACTIVE MISSION",
                  subtitle: Text(
                    currentEvId,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  actions: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(20),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(0.2),
                            blurRadius: 8,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      child: DropdownButtonHideUnderline(
                        child: DropdownButton<String>(
                          value: currentEvId,
                          icon: const Icon(Icons.keyboard_arrow_down, color: Color(0xFF2ECC71)),
                          style: const TextStyle(
                            color: Colors.black87,
                            fontWeight: FontWeight.bold,
                          ),
                          items: List.generate(50, (index) => "EV_$index")
                              .map((id) => DropdownMenuItem(
                                    value: id,
                                    child: Text(id),
                                  ))
                              .toList(),
                          onChanged: (val) {
                            if (val != null) _switchVehicle(val);
                          },
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              // 3. BOTTOM STATS PANEL
              Positioned(
                bottom: 30,
                left: 16,
                right: 16,
                child: DashboardStatsPanel(
                  speed: _status.speed,
                  eta: _status.eta,
                  distToTls: _status.distToTls,
                  isGreenWaveActive: _status.isGreenWaveActive,
                ),
              ),

              // 4. GREEN WAVE BANNER (Floating below top bar)
              if (_status.isGreenWaveActive)
                Positioned(
                  top: 120,
                  left: 16,
                  right: 16,
                  child: Center(
                    child: GreenWaveBanner(
                      activeJunctionsCount: _status.activeJunctions.length,
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}
