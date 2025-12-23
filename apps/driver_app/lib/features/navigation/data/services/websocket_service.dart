import 'dart:convert';
import 'dart:async';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../../../core/constants/app_constants.dart';
import '../models/vehicle_status.dart';

class WebSocketService {
  late WebSocketChannel _channel;
  late Stream<VehicleStatus> _vehicleStatusStream;
  
  WebSocketService() {
    connect();
  }

  void connect() {
    print("Connecting to WebSocket: ${AppConstants.webSocketUrl}");
    try {
      _channel = WebSocketChannel.connect(
        Uri.parse(AppConstants.webSocketUrl),
      );
      
      // Initialize the broadcast stream once
      _vehicleStatusStream = _channel.stream.map((data) {
        try {
          // Debug print to see raw data
          // print("Raw WS Data: $data"); 
          final decoded = jsonDecode(data);
          if (decoded['type'] == 'status') {
            return VehicleStatus.fromJson(decoded);
          }
          return VehicleStatus.empty();
        } catch (e) {
          print("Parse Error: $e");
          return VehicleStatus.empty();
        }
      }).asBroadcastStream();
      
    } catch (e) {
      print("Connection Error: $e");
    }
  }

  void dispose() {
    _channel.sink.close();
  }

  void switchVehicle(String newId) {
    print("Switching to vehicle: $newId");
    _channel.sink.add(jsonEncode({
      "type": "switch_ev",
      "ev_id": newId
    }));
  }

  Stream<VehicleStatus> get vehicleStatusStream => _vehicleStatusStream;
  
  // Expose raw stream for debug if needed
  Stream<dynamic> get rawStream => _channel.stream;
}
