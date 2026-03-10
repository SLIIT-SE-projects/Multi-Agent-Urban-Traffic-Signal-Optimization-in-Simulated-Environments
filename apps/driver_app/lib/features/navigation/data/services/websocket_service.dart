import 'dart:convert';
import 'dart:async';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../../core/constants/app_constants.dart';
import '../models/vehicle_status.dart';

class WebSocketService {
  WebSocketChannel? _channel;
  final StreamController<VehicleStatus> _statusController = StreamController<VehicleStatus>.broadcast();
  final StreamController<bool> _connectionStateController = StreamController<bool>.broadcast();
  bool _isIntentionalDisconnect = false;
  
  WebSocketService() {
    _connectionStateController.add(false); // Initial state
    connect();
  }

  Future<void> connect() async {
    _isIntentionalDisconnect = false;
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
      
      // Assume connected once we start listening successfully
      if (!_connectionStateController.isClosed) {
        _connectionStateController.add(true); 
      }

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
        if (!_connectionStateController.isClosed) {
          _connectionStateController.add(false);
        }
        _reconnect();
      }, onDone: () {
        print("WebSocket Closed");
        if (!_connectionStateController.isClosed) {
          _connectionStateController.add(false);
        }
        _reconnect();
      });
      
    } catch (e) {
      print("Connection Error: $e");
      if (!_connectionStateController.isClosed) {
        _connectionStateController.add(false);
      }
      _reconnect();
    }
  }

  void _reconnect() {
    if (_isIntentionalDisconnect) return;
    
    print("Attempting to reconnect in 3 seconds...");
    _channel?.sink.close(); // Ensure old channel is closed
    
    Future.delayed(const Duration(seconds: 3), () {
      if (!_isIntentionalDisconnect) {
        connect();
      }
    });
  }

  void dispose() {
    _isIntentionalDisconnect = true;
    _channel?.sink.close();
    _statusController.close();
    _connectionStateController.close();
  }

  void switchVehicle(String newId) {
    print("Switching to vehicle: $newId");
    _channel?.sink.add(jsonEncode({
      "type": "switch_ev",
      "ev_id": newId
    }));
  }

  Stream<VehicleStatus> get vehicleStatusStream => _statusController.stream;
  Stream<bool> get connectionState => _connectionStateController.stream;
  
  // Expose raw stream for debug if needed
  Stream<dynamic>? get rawStream => _channel?.stream;
}
