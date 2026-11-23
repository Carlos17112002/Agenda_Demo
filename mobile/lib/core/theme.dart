import 'package:flutter/material.dart';

import 'branding.dart';

class AgendaColors {
  static const black = Color(0xFF090909);
  static const surface = Color(0xFF151515);
  static const red = Color(0xFFE50914);
  static const darkRed = Color(0xFF8B0000);
  static const white = Color(0xFFFFFFFF);
  static const border = Color(0xFF252525);
  static const muted = Color(0xFFA0A0A0);
  static const lightSurface = Color(0xFFF6F6F8);
  static const lightBorder = Color(0xFFE4E4E9);
  static const lightMuted = Color(0xFF5F636B);
  static const lightText = Color(0xFF121317);
}

class AgendaPalette extends ThemeExtension<AgendaPalette> {
  const AgendaPalette({
    required this.background,
    required this.surface,
    required this.surfaceAlt,
    required this.border,
    required this.muted,
    required this.onSurface,
  });

  final Color background;
  final Color surface;
  final Color surfaceAlt;
  final Color border;
  final Color muted;
  final Color onSurface;

  static const light = AgendaPalette(
    background: Colors.white,
    surface: AgendaColors.lightSurface,
    surfaceAlt: Colors.white,
    border: AgendaColors.lightBorder,
    muted: AgendaColors.lightMuted,
    onSurface: AgendaColors.lightText,
  );

  static const dark = AgendaPalette(
    background: AgendaColors.black,
    surface: AgendaColors.surface,
    surfaceAlt: Color(0xFF1C1C1C),
    border: AgendaColors.border,
    muted: AgendaColors.muted,
    onSurface: AgendaColors.white,
  );

  @override
  AgendaPalette copyWith({
    Color? background,
    Color? surface,
    Color? surfaceAlt,
    Color? border,
    Color? muted,
    Color? onSurface,
  }) {
    return AgendaPalette(
      background: background ?? this.background,
      surface: surface ?? this.surface,
      surfaceAlt: surfaceAlt ?? this.surfaceAlt,
      border: border ?? this.border,
      muted: muted ?? this.muted,
      onSurface: onSurface ?? this.onSurface,
    );
  }

  @override
  AgendaPalette lerp(AgendaPalette? other, double t) {
    if (other == null) return this;
    return AgendaPalette(
      background: Color.lerp(background, other.background, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      surfaceAlt: Color.lerp(surfaceAlt, other.surfaceAlt, t)!,
      border: Color.lerp(border, other.border, t)!,
      muted: Color.lerp(muted, other.muted, t)!,
      onSurface: Color.lerp(onSurface, other.onSurface, t)!,
    );
  }
}

extension AgendaThemeX on BuildContext {
  AgendaPalette get palette =>
      Theme.of(this).extension<AgendaPalette>() ??
      (Theme.of(this).brightness == Brightness.dark
          ? AgendaPalette.dark
          : AgendaPalette.light);
}

ThemeData buildAgendaTheme([Branding branding = Branding.fallback]) {
  final dark = branding.isDark;
  final palette = dark ? AgendaPalette.dark : AgendaPalette.light;
  final scheme = dark
      ? ColorScheme.dark(
          primary: branding.primary,
          onPrimary: branding.onPrimary,
          secondary: branding.secondary,
          onSecondary: branding.onSecondary,
          surface: palette.surface,
          onSurface: palette.onSurface,
          onSurfaceVariant: palette.muted,
          error: AgendaColors.red,
          onError: AgendaColors.white,
          outline: palette.border,
        )
      : ColorScheme.light(
          primary: branding.primary,
          onPrimary: branding.onPrimary,
          secondary: branding.secondary,
          onSecondary: branding.onSecondary,
          surface: palette.surface,
          onSurface: palette.onSurface,
          onSurfaceVariant: palette.muted,
          error: const Color(0xFFC62828),
          onError: AgendaColors.white,
          outline: palette.border,
        );
  final base = ThemeData(
    useMaterial3: true,
    brightness: branding.brightness,
    colorScheme: scheme,
    scaffoldBackgroundColor: palette.background,
    extensions: [palette],
  );
  return base.copyWith(
    textTheme: base.textTheme.apply(
      bodyColor: palette.onSurface,
      displayColor: palette.onSurface,
    ),
    iconTheme: IconThemeData(color: palette.onSurface),
    appBarTheme: AppBarTheme(
      backgroundColor: palette.background,
      foregroundColor: palette.onSurface,
      elevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardThemeData(
      color: palette.surface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: palette.border),
      ),
      margin: EdgeInsets.zero,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: palette.surfaceAlt,
      hintStyle: TextStyle(color: palette.muted),
      labelStyle: TextStyle(color: palette.muted),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: palette.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: palette.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: branding.primary, width: 1.4),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: branding.primary,
        foregroundColor: branding.onPrimary,
        minimumSize: const Size.fromHeight(50),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontWeight: FontWeight.w700),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: palette.onSurface,
        side: BorderSide(color: palette.border),
        minimumSize: const Size.fromHeight(48),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(foregroundColor: branding.primary),
    ),
    floatingActionButtonTheme: FloatingActionButtonThemeData(
      backgroundColor: branding.primary,
      foregroundColor: branding.onPrimary,
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: branding.primary,
    ),
    dividerTheme: DividerThemeData(color: palette.border),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: dark ? palette.surfaceAlt : palette.onSurface,
      contentTextStyle: TextStyle(
        color: dark ? palette.onSurface : AgendaColors.white,
      ),
      behavior: SnackBarBehavior.floating,
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: palette.surface,
      indicatorColor: branding.primary.withValues(alpha: 0.22),
      labelTextStyle: WidgetStateProperty.all(
        TextStyle(color: palette.onSurface, fontSize: 12),
      ),
      iconTheme: WidgetStateProperty.resolveWith(
        (states) => IconThemeData(
          color: states.contains(WidgetState.selected)
              ? branding.primary
              : palette.muted,
        ),
      ),
    ),
  );
}
