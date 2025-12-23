import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static ThemeData get darkTheme {
    return ThemeData.dark().copyWith(
      scaffoldBackgroundColor: const Color(0xFF1E1E1E),
      textTheme: GoogleFonts.robotoMonoTextTheme(ThemeData.dark().textTheme),
    );
  }
}
