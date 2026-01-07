import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import '../../../../core/constants/app_constants.dart';

class LiveMap extends StatelessWidget {
  final MapController mapController;
  final LatLng evPosition;
  final List<Map<String, dynamic>> activeJunctions;
  final bool hasData;

  const LiveMap({
    super.key,
    required this.mapController,
    required this.evPosition,
    required this.activeJunctions,
    required this.hasData,
  });

  @override
  Widget build(BuildContext context) {
    return FlutterMap(
      mapController: mapController,
      options: MapOptions(
        initialCenter: AppConstants.defaultMapCenter, // Rajagiriya, Sri Lanka
        initialZoom: 16.0,
      ),
      children: [
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.evps.app',
        ),
        if (hasData)
          MarkerLayer(
            markers: [
              // 1. EMERGENCY VEHICLE MARKER
              Marker(
                point: evPosition,
                width: 50,
                height: 50,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    // Pulse Effect
                    Container(
                      width: 50,
                      height: 50,
                      decoration: BoxDecoration(
                        color: Colors.blueAccent.withOpacity(0.2),
                        shape: BoxShape.circle,
                      ),
                    ),
                    // Main Icon Background
                    Container(
                        width: 36,
                        height: 36,
                        decoration: BoxDecoration(
                          color: Colors.white,
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 2),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.3),
                              blurRadius: 8,
                              offset: const Offset(0, 3),
                            ),
                          ],
                        ),
                        child: const Center(
                          child: Icon(
                            Icons.emergency_rounded, 
                            color: Colors.redAccent,
                            size: 20,
                          ),
                        )),
                  ],
                ),
              ),

              // 2. ACTIVE TRAFFIC LIGHTS (GREEN WAVE)
              for (var junction in activeJunctions)
                Marker(
                  point: LatLng(junction['lat'], junction['lon']),
                  width: 40,
                  height: 40,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      // Glow Effect
                      Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          color: const Color(0xFF00E676).withOpacity(0.3),
                          shape: BoxShape.circle,
                        ),
                      ),
                      // Core Light
                      Container(
                        width: 20,
                        height: 20,
                        decoration: BoxDecoration(
                          color: const Color(0xFF00E676),
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 2),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.2),
                              blurRadius: 6,
                              offset: const Offset(0, 3),
                            ),
                          ],
                        ),
                        child: const Icon(
                          Icons.check, // Or just blank, but check adds a nice touch for "Go"
                          color: Colors.white,
                          size: 14,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
      ],
    );
  }
}
