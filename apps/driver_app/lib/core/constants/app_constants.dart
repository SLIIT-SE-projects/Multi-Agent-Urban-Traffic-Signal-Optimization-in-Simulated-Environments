import 'package:latlong2/latlong.dart';

class AppConstants {
  static String serverIpAddress = 'localhost';
  static String get webSocketUrl => 'ws://$serverIpAddress:5000/ws';
  
  static const String defaultEvId = 'EV_0';

  // Map Constants - Colombo/Rajagiriya area
  static const LatLng defaultMapCenter = LatLng(7.166139, 79.893583);
}