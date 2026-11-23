import { describe, expect, test } from 'vitest';

import { applyBrandTheme, contrastRatio, normalizeHex, readableForeground } from './colors';

describe('colors', () => {
  test('normaliza colores hexadecimales de seis dígitos', () => {
    expect(normalizeHex('#AABBCC')).toBe('#aabbcc');
    expect(normalizeHex('aabbcc')).toBe('#aabbcc');
    expect(normalizeHex('#abc')).toBeNull();
  });

  test('calcula el contraste entre blanco y negro', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 0);
  });

  test('elige texto oscuro sobre un fondo claro', () => {
    expect(readableForeground('#facc15')).toBe('#0f172a');
    expect(readableForeground('#111827')).toBe('#ffffff');
  });

  test('aplica las variables de marca al documento', () => {
    applyBrandTheme({ primary_color: '#10b981', secondary_color: '#065f46' });
    const style = document.documentElement.style;
    expect(style.getPropertyValue('--brand-primary')).toBe('#10b981');
    expect(style.getPropertyValue('--brand-secondary')).toBe('#065f46');
    expect(style.getPropertyValue('--brand-fg')).toBe('#0f172a');
  });
});
