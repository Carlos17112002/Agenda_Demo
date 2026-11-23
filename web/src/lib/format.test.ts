import { describe, expect, test } from 'vitest';

import { BOOKING_STATUS_LABELS, formatMoney, formatPercent, weekdayLabel } from './format';

describe('formato', () => {
  test('formatea montos y porcentajes en español de Chile', () => {
    expect(formatMoney('12000.00')).toBe('$ 12.000');
    expect(formatMoney(1234.5)).toBe('$ 1.234,5');
    expect(formatPercent('37.50')).toBe('37,5 %');
  });

  test('traduce estados y días', () => {
    expect(BOOKING_STATUS_LABELS.no_show).toBe('No asistió');
    expect(BOOKING_STATUS_LABELS.confirmed).toBe('Confirmada');
    expect(weekdayLabel(0)).toBe('Lunes');
  });
});
