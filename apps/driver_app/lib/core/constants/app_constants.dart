import 'package:latlong2/latlong.dart';

class AppConstants {
  static String serverIpAddress = '10.0.2.2';
  static String get webSocketUrl => 'ws://$serverIpAddress:5000/ws';
  
  static const String defaultEvId = 'EV_0';

  // Map Constants - Colombo/Rajagiriya area
  static const LatLng defaultMapCenter = LatLng(6.9080, 79.8970);
}