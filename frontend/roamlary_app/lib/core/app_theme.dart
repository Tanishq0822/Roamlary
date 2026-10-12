import 'package:flutter/material.dart';

/// Roamlary brand theme — owner-directed palette: a clean WHITE background
/// with LIGHT GREEN as the primary accent and LIGHT PURPLE as the secondary
/// accent. Red stays reserved strictly for SOS/emergency affordances so it
/// always means "danger".
class AppTheme {
  AppTheme._();

  // Brand palette.
  static const Color seed = Color(0xFF66BB6A); // green accent (buttons/FABs)
  static const Color green = Color(0xFF43A047); // deeper green for text/pills
  static const Color lightGreen = Color(0xFFA5D6A7); // soft green fill
  static const Color greenTint = Color(0xFFEDF7EE); // near-white green surface
  static const Color purple = Color(0xFF7E57C2); // deeper purple for text/pills
  static const Color lightPurple = Color(0xFFB39DDB); // soft purple fill
  static const Color purpleTint = Color(0xFFF4EFFB); // near-white purple surface
  static const Color danger = Color(0xFFDC2626); // red-600
  static const Color dangerDark = Color(0xFFB91C1C); // red-700
  // Historical name kept for older call sites; now the green tint.
  static const Color surfaceTint = greenTint;

  static ThemeData light() {
    final scheme = ColorScheme.fromSeed(seedColor: seed).copyWith(
      surface: Colors.white,
      secondary: purple,
      secondaryContainer: purpleTint,
      tertiary: green,
      surfaceContainerLow: greenTint,
    );
    return _base(scheme, background: Colors.white);
  }

  static ThemeData dark() {
    final scheme = ColorScheme.fromSeed(
      seedColor: seed,
      brightness: Brightness.dark,
    );
    return _base(scheme);
  }

  static ThemeData _base(ColorScheme scheme, {Color? background}) {
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: background ?? scheme.surface,
      appBarTheme: AppBarTheme(
        centerTitle: false,
        elevation: 0,
        backgroundColor: background ?? scheme.surface,
        foregroundColor: scheme.onSurface,
        titleTextStyle: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          color: scheme.onSurface,
        ),
      ),
      // White cards with a soft green hairline so they read on the white
      // scaffold. CardThemeData is the Flutter >= 3.27 parameter type.
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: lightGreen.withValues(alpha: 0.7)),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerLow,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 68,
        backgroundColor: Colors.white,
        indicatorColor: scheme.primaryContainer, // light green selection pill
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
    );
  }
}
