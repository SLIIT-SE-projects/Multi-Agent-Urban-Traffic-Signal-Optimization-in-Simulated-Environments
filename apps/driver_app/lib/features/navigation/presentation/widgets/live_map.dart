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
                  width: 30,
                  height: 45,
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      // Traffic Light Body
                      Container(
                        width: 18,
                        height: 30,
                        padding: const EdgeInsets.symmetric(vertical: 3),
                        decoration: BoxDecoration(
                          color: const Color(0xFF2D3436), // Dark slate
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: Colors.white, width: 1),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.3),
                              blurRadius: 4,
                              offset: const Offset(0, 2),
                            ),
                          ],
                        ),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                          children: [
                            // Red (Off)
                            Container(
                              width: 6,
                              height: 6,
                              decoration: BoxDecoration(
                                color: Colors.red.withOpacity(0.3),
                                shape: BoxShape.circle,
                              ),
                            ),
                            // Yellow (Off)
                            Container(
                              width: 6,
                              height: 6,
                              decoration: BoxDecoration(
                                color: Colors.amber.withOpacity(0.3),
                                shape: BoxShape.circle,
                              ),
                            ),
                            // Green (Active & Glowing)
                            Container(
                              width: 8,
                              height: 8,
                              decoration: BoxDecoration(
                                color: const Color(0xFF00E676),
                                shape: BoxShape.circle,
                                boxShadow: [
                                  BoxShadow(
                                    color: const Color(0xFF00E676).withOpacity(0.6),
                                    blurRadius: 4,
                                    spreadRadius: 1.5,
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                      // Pole
                      Container(
                        width: 3,
                        height: 8,
                        color: Colors.grey[800],
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
