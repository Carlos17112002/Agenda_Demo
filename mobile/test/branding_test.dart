import 'package:agenda_mobile/core/branding.dart';
import 'package:agenda_mobile/widgets/common.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('fromCompany prefers display name and parses brand colors', () {
    final branding = Branding.fromCompany({
      'name': 'Estudio Aurora SpA',
      'display_name': 'Estudio Aurora',
      'primary_color': '#10B981',
      'secondary_color': '#047857',
      'logo_url': 'https://example.com/logo.png',
    });

    expect(branding.displayName, 'Estudio Aurora');
    expect(branding.primary, const Color(0xFF10B981));
    expect(branding.secondary, const Color(0xFF047857));
    expect(branding.hasLogo, isTrue);
  });

  test('fromCompany falls back on missing or invalid brand values', () {
    final branding = Branding.fromCompany({
      'name': 'Demo',
      'primary_color': 'red',
    });

    expect(branding.displayName, 'Demo');
    expect(branding.primary, Branding.fallback.primary);
    expect(branding.secondary, Branding.fallback.secondary);
    expect(branding.hasLogo, isFalse);
  });

  test('parseHex accepts six digit hex with or without hash', () {
    expect(
      Branding.parseHex('#0a0A0a', Colors.white),
      const Color(0xFF0A0A0A),
    );
    expect(
      Branding.parseHex('ffffff', Colors.black),
      const Color(0xFFFFFFFF),
    );
    expect(Branding.parseHex('#GGGGGG', Colors.red), Colors.red);
  });

  test('fromCompany reads the background mode and defaults to light', () {
    final light = Branding.fromCompany({'name': 'Demo'});
    final dark = Branding.fromCompany({
      'name': 'Demo',
      'theme_mode': 'dark',
    });

    expect(light.brightness, Brightness.light);
    expect(dark.brightness, Brightness.dark);
    expect(Branding.fallback.brightness, Brightness.light);
  });

  test('onPrimary keeps text readable for light and dark brands', () {
    const light = Branding(
      displayName: 'Claro',
      primary: Color(0xFFFFF59D),
      secondary: Color(0xFFFFFFFF),
    );
    const dark = Branding(
      displayName: 'Oscuro',
      primary: Color(0xFF090909),
      secondary: Color(0xFF8B0000),
    );

    expect(light.onPrimary, const Color(0xFF090909));
    expect(dark.onPrimary, Colors.white);
  });

  testWidgets('CompanyLogo falls back to the company initial', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: CompanyLogo(company: {'name': 'Aurora'})),
      ),
    );

    expect(find.text('A'), findsOneWidget);
  });
}
