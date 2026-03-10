import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: const Color(0xFFF5F5F5), // White/Light Grey
      primaryColor: const Color(0xFF2ECC71), // Emerald Green
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xFF2ECC71),
        primary: const Color(0xFF2ECC71),
        surface: const Color(0xFFF5F5F5),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.white,
        foregroundColor: Colors.black, // Text color
        elevation: 0,
        centerTitle: true,
      ),
      textTheme: GoogleFonts.robotoMonoTextTheme(
        ThemeData.light().textTheme.apply(
              bodyColor: Colors.black, // Dark Grey/Black for readability
              displayColor: Colors.black,
            ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF2ECC71), // Green background
          foregroundColor: Colors.white, // White text
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12), // Rounded corners
          ),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
        ),
      ),
    );
  }
}
