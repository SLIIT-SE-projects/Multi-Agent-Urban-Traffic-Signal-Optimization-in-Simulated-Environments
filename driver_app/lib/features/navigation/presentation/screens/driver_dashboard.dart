import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import '../../data/models/vehicle_status.dart';
import '../../data/services/websocket_service.dart';
import '../widgets/dashboard_stats_panel.dart';
import '../widgets/green_wave_banner.dart';
import '../widgets/live_map.dart';
import '../../../../core/constants/app_constants.dart';

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
      // --- APP BAR ---
      appBar: AppBar(
        title: const Text("EVPS PRIORITY SYSTEM"),
        backgroundColor: _status.isGreenWaveActive ? Colors.green[800] : Colors.grey[900],
        elevation: 0,
        actions: [
          // Vehicle Switcher Dropdown
          DropdownButton<String>(
            value: currentEvId,
            dropdownColor: Colors.grey[800],
            underline: Container(),
            items: List.generate(50, (index) => "EV_$index")
                .map((id) => DropdownMenuItem(
                      value: id,
                      child: Text(id, style: const TextStyle(color: Colors.white)),
                    ))
                .toList(),
            onChanged: (val) {
              if (val != null) _switchVehicle(val);
            },
          ),
          const SizedBox(width: 20),
        ],
      ),

      // --- BODY ---
      body: StreamBuilder<VehicleStatus>(
        stream: _webSocketService.vehicleStatusStream,
        builder: (context, snapshot) {
          if (snapshot.hasData) {
            _status = snapshot.data!;
            
            // Logic to move map only if data is valid and changed significantly could be added here,
            // but for parity with original, we'll check if we have valid non-zero data.
            if (_status.position.latitude != 0 && _status.position.longitude != 0) {
               hasData = true;
               // Move map to vehicle position. 
               // Note: Calling move inside build can be problematic, but was in original. 
               // Better is to use a listener or just ensure it doesn't loop. 
               // For now, we keep it simple but safe via post-frame callback if strictly needed, 
               // but mapController.move is often okay if not fighting user interaction.
               // To avoid rebuild loops, we can check distance or just do it.
               try {
                 _mapController.move(_status.position, 16.0);
               } catch (e) {
                 // Controller might not be ready
               }
            }
          }

          return Stack(
            children: [
              // 1. MAP LAYER
              LiveMap(
                mapController: _mapController,
                evPosition: _status.position,
                activeJunctions: _status.activeJunctions,
                hasData: hasData,
              ),

              // 2. DASHBOARD OVERLAY
              Positioned(
                bottom: 30,
                left: 20,
                right: 20,
                child: DashboardStatsPanel(
                  speed: _status.speed,
                  eta: _status.eta,
                  distToTls: _status.distToTls,
                  isGreenWaveActive: _status.isGreenWaveActive,
                ),
              ),

              // 3. GREEN WAVE ALERT
              if (_status.isGreenWaveActive)
                Positioned(
                  top: 10,
                  left: 20,
                  right: 20,
                  child: GreenWaveBanner(
                    activeJunctionsCount: _status.activeJunctions.length,
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}
