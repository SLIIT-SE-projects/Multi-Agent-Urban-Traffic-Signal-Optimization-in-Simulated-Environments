import 'dart:convert';
import 'dart:async';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../../core/constants/app_constants.dart';
import '../models/vehicle_status.dart';

class WebSocketService {
  WebSocketChannel? _channel;
  final StreamController<VehicleStatus> _statusController = StreamController<VehicleStatus>.broadcast();
  
  WebSocketService() {
    connect();
  }

  Future<void> connect() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final savedIp = prefs.getString('serverIpAddress');
      if (savedIp != null && savedIp.isNotEmpty) {
        AppConstants.serverIpAddress = savedIp;
      }
    } catch (e) {
      print("Error loading IP address: $e");
    }

    print("Connecting to WebSocket: ${AppConstants.webSocketUrl}");
    try {
      _channel = WebSocketChannel.connect(
        Uri.parse(AppConstants.webSocketUrl),
      );
      
      _channel!.stream.listen((data) {
        try {
          final decoded = jsonDecode(data);
          if (decoded['type'] == 'status') {
             if (!_statusController.isClosed) {
              _statusController.add(VehicleStatus.fromJson(decoded));
             }
          } else {
             if (!_statusController.isClosed) {
              _statusController.add(VehicleStatus.empty());
             }
          }
        } catch (e) {
          print("Parse Error: $e");
          if (!_statusController.isClosed) {
            _statusController.add(VehicleStatus.empty());
          }
        }
      }, onError: (error) {
        print("WebSocket Error: $error");
      }, onDone: () {
        print("WebSocket Closed");
      });
      
    } catch (e) {
      print("Connection Error: $e");
    }
  }

  void dispose() {
    _channel?.sink.close();
    _statusController.close();
  }

  void switchVehicle(String newId) {
    print("Switching to vehicle: $newId");
    _channel?.sink.add(jsonEncode({
      "type": "switch_ev",
      "ev_id": newId
    }));
  }

  Stream<VehicleStatus> get vehicleStatusStream => _statusController.stream;
  
  // Expose raw stream for debug if needed
  Stream<dynamic>? get rawStream => _channel?.stream;
}
