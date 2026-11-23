import 'package:agenda_mobile/core/branding.dart';
import 'package:agenda_mobile/core/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('theme applies company brand colors to primary controls', () {
    const branding = Branding(
      displayName: 'Aurora',
      primary: Color(0xFF10B981),
      secondary: Color(0xFF047857),
      brightness: Brightness.dark,
    );

    final theme = buildAgendaTheme(branding);

    expect(theme.colorScheme.primary, branding.primary);
    expect(theme.colorScheme.secondary, branding.secondary);
    expect(theme.colorScheme.brightness, Brightness.dark);
    expect(theme.floatingActionButtonTheme.backgroundColor, branding.primary);
    expect(theme.progressIndicatorTheme.color, branding.primary);
    expect(
      theme.textButtonTheme.style?.foregroundColor?.resolve({}),
      branding.primary,
    );
  });

  test('default theme uses a light background with the AGENDA red palette', () {
    final theme = buildAgendaTheme();

    expect(theme.colorScheme.primary, AgendaColors.red);
    expect(theme.colorScheme.secondary, AgendaColors.darkRed);
    expect(theme.colorScheme.brightness, Brightness.light);
    expect(theme.scaffoldBackgroundColor, Colors.white);
    expect(theme.colorScheme.onSurface, const Color(0xFF121317));
  });

  test('light theme keeps branded accents on white surfaces', () {
    const branding = Branding(
      displayName: 'Aurora',
      primary: Color(0xFF10B981),
      secondary: Color(0xFF047857),
    );

    final theme = buildAgendaTheme(branding);

    expect(theme.brightness, Brightness.light);
    expect(theme.colorScheme.primary, branding.primary);
    expect(theme.colorScheme.surface, const Color(0xFFF6F6F8));
    expect(theme.colorScheme.onSurface, const Color(0xFF121317));
    expect(theme.colorScheme.outline, const Color(0xFFE4E4E9));
    expect(theme.colorScheme.onSurfaceVariant, const Color(0xFF5F636B));
  });

  test('dark branding keeps light text on dark surfaces', () {
    const branding = Branding(
      displayName: 'Aurora',
      primary: Color(0xFF10B981),
      secondary: Color(0xFF047857),
      brightness: Brightness.dark,
    );

    final theme = buildAgendaTheme(branding);

    expect(theme.scaffoldBackgroundColor, const Color(0xFF090909));
    expect(theme.colorScheme.onSurface, Colors.white);
  });
}
