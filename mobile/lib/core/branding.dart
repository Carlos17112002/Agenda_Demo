import 'package:flutter/material.dart';

class Branding {
  const Branding({
    required this.displayName,
    required this.primary,
    required this.secondary,
    this.logoUrl = '',
    this.brightness = Brightness.light,
  });

  final String displayName;
  final Color primary;
  final Color secondary;
  final String logoUrl;
  final Brightness brightness;

  static const fallback = Branding(
    displayName: 'AGENDA',
    primary: Color(0xFFE50914),
    secondary: Color(0xFF8B0000),
  );

  Color get onPrimary => _onColor(primary);
  Color get onSecondary => _onColor(secondary);

  bool get hasLogo => logoUrl.trim().isNotEmpty;
  bool get isDark => brightness == Brightness.dark;

  factory Branding.fromCompany(
    Map<String, dynamic> company, {
    String fallbackName = 'Empresa',
  }) {
    final name = (company['display_name'] ?? company['name'] ?? '')
        .toString()
        .trim();
    return Branding(
      displayName: name.isEmpty ? fallbackName : name,
      primary: parseHex(company['primary_color'], fallback.primary),
      secondary: parseHex(company['secondary_color'], fallback.secondary),
      logoUrl: (company['logo_url'] ?? '').toString().trim(),
      brightness: company['theme_mode'] == 'dark'
          ? Brightness.dark
          : Brightness.light,
    );
  }

  static Color parseHex(dynamic value, Color fallbackColor) {
    final raw = value?.toString().trim().replaceFirst('#', '');
    if (raw == null || !RegExp(r'^[0-9a-fA-F]{6}$').hasMatch(raw)) {
      return fallbackColor;
    }
    return Color(int.parse('FF$raw', radix: 16));
  }

  static Color _onColor(Color color) =>
      ThemeData.estimateBrightnessForColor(color) == Brightness.dark
      ? Colors.white
      : const Color(0xFF090909);
}
