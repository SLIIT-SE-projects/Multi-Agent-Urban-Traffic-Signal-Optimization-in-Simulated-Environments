import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../../../../core/constants/app_constants.dart';

class LocationPickerScreen extends StatefulWidget {
  const LocationPickerScreen({super.key});

  @override
  State<LocationPickerScreen> createState() => _LocationPickerScreenState();
}

class _LocationPickerScreenState extends State<LocationPickerScreen> {
  final MapController _mapController = MapController();
  LatLng? _selectedLocation;
  LatLng _initialCenter = AppConstants.defaultMapCenter;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchMapCenter();
  }

  Future<void> _fetchMapCenter() async {
    try {
      final url = Uri.parse('http://${AppConstants.serverIpAddress}:5000/api/simulation/topology');
      final response = await http.get(url);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data != null && data['center_lat'] != null && data['center_lon'] != null) {
          setState(() {
            _initialCenter = LatLng(
              data['center_lat'].toDouble(),
              data['center_lon'].toDouble(),
            );
          });
        }
      }
    } catch (e) {
      print('Error fetching map center: $e');
      // Fallback to defaultMapCenter
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  void _handleTap(TapPosition tapPosition, LatLng point) {
    setState(() {
      _selectedLocation = point;
    });
  }

  void _confirmSelection() {
    if (_selectedLocation != null) {
      Navigator.pop(context, _selectedLocation);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please tap on the map to select a location')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Pick Location'),
        centerTitle: true,
        backgroundColor: Colors.white,
        foregroundColor: Colors.black,
        elevation: 0,
      ),
      body: Stack(
        children: [
          if (_isLoading)
            const Center(
              child: CircularProgressIndicator(),
            )
          else
            FlutterMap(
              mapController: _mapController,
              options: MapOptions(
                initialCenter: _initialCenter,
                initialZoom: 15.0,
                onTap: _handleTap,
              ),
            children: [
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.evps.app',
              ),
              if (_selectedLocation != null)
                MarkerLayer(
                  markers: [
                    Marker(
                      point: _selectedLocation!,
                      width: 50,
                      height: 50,
                      child: const Icon(
                        Icons.location_on,
                        color: Colors.red,
                        size: 50,
                      ),
                      alignment: Alignment.topCenter,
                    ),
                  ],
                ),
            ],
          ),
          
          // Instructions Banner
          Positioned(
            top: 16,
            left: 16,
            right: 16,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.1),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Row(
                children: [
                   Icon(Icons.touch_app, color: Colors.blue[700]),
                   const SizedBox(width: 12),
                   const Expanded(
                     child: Text(
                       'Tap anywhere on the map to set the location.',
                       style: TextStyle(fontWeight: FontWeight.w500),
                     ),
                   ),
                ],
              ),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _confirmSelection,
        backgroundColor: _selectedLocation == null ? Colors.grey : Theme.of(context).primaryColor,
        icon: const Icon(Icons.check),
        label: const Text('Confirm Location'),
      ),
    );
  }
}
