import 'package:latlong2/latlong.dart';

class VehicleStatus {
  final double speed;
  final double eta;
  final double distToTls;
  final bool isGreenWaveActive;
  final String currentTls;
  final LatLng position;
  final List<Map<String, dynamic>> activeJunctions;
  final List<String> activeFleet;

  VehicleStatus({
    required this.speed,
    required this.eta,
    required this.distToTls,
    required this.isGreenWaveActive,
    required this.currentTls,
    required this.position,
    required this.activeJunctions,
    required this.activeFleet,
  });

  factory VehicleStatus.empty() {
    return VehicleStatus(
      speed: 0.0,
      eta: 0.0,
      distToTls: 0.0,
      isGreenWaveActive: false,
      currentTls: "",
      position: const LatLng(0, 0),
      activeJunctions: [],
      activeFleet: [],
    );
  }

  factory VehicleStatus.fromJson(Map<String, dynamic> json) {
    // Parse Active Junctions
    List<Map<String, dynamic>> junctions = [];
    if (json.containsKey('active_junctions')) {
      for (var j in json['active_junctions']) {
        if (j['lat'] != 0.0 && j['lon'] != 0.0) {
          junctions.add(j);
        }
      }
    }

    double lat = json['lat'] != null ? (json['lat'] as num).toDouble() : 0.0;
    double lon = json['lon'] != null ? (json['lon'] as num).toDouble() : 0.0;

    List<String> parsedFleet = [];
    if (json.containsKey('active_fleet') && json['active_fleet'] != null) {
      parsedFleet = List<String>.from(json['active_fleet']);
    }

    return VehicleStatus(
      speed: json['speed'] != null ? (json['speed'] as num).toDouble() : 0.0,
      eta: json['eta'] != null ? (json['eta'] as num).toDouble() : 0.0,
      distToTls: json['dist_to_tls'] != null ? (json['dist_to_tls'] as num).toDouble() : 0.0,
      isGreenWaveActive: json['green_wave_active'] ?? false,
      currentTls: json['tls_id'] ?? "",
      position: LatLng(lat, lon),
      activeJunctions: junctions,
      activeFleet: parsedFleet,
    );
  }
}
