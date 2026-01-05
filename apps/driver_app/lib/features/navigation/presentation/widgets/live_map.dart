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
              Marker(
                point: evPosition,
                width: 80,
                height: 80,
                child: const Icon(
                  Icons.local_hospital,
                  color: Colors.blueAccent,
                  size: 40,
                ),
              ),
              // Active Green Wave Junctions
              for (var junction in activeJunctions)
                Marker(
                  point: LatLng(junction['lat'], junction['lon']),
                  width: 40,
                  height: 40,
                  child: const Icon(
                    Icons.traffic,
                    color: Colors.greenAccent,
                    size: 30,
                  ),
                ),
            ],
          ),
      ],
    );
  }
}
