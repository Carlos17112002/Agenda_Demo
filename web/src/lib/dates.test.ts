import { describe, expect, test } from 'vitest';

import {
  dateTimeLocalToISO,
  formatTime,
  isoToDateTimeLocal,
  shiftDate,
  todayInZone,
  weekRange,
} from './dates';

describe('fechas de agenda', () => {
  test('calcula el día local de la sucursal y no el UTC', () => {
    expect(todayInZone('America/Santiago', new Date('2026-11-12T02:00:00Z'))).toBe('2026-11-11');
    expect(todayInZone('America/Santiago', new Date('2026-11-11T12:00:00Z'))).toBe('2026-11-11');
  });

  test('la semana corre de lunes a domingo', () => {
    expect(weekRange('2026-11-11')).toEqual({ date_from: '2026-11-09', date_to: '2026-11-15' });
    expect(weekRange('2026-11-15')).toEqual({ date_from: '2026-11-09', date_to: '2026-11-15' });
  });

  test('desplaza días cruzando meses', () => {
    expect(shiftDate('2026-11-30', 1)).toBe('2026-12-01');
    expect(shiftDate('2026-01-01', -1)).toBe('2025-12-31');
  });

  test('convierte hora local de verano e invierno a UTC', () => {
    expect(dateTimeLocalToISO('2026-01-15T10:00', 'America/Santiago')).toBe(
      '2026-01-15T13:00:00.000Z',
    );
    expect(dateTimeLocalToISO('2026-07-15T10:00', 'America/Santiago')).toBe(
      '2026-07-15T14:00:00.000Z',
    );
  });

  test('convierte un instante UTC a hora local de la sucursal', () => {
    expect(isoToDateTimeLocal('2026-01-15T13:00:00Z', 'America/Santiago')).toBe('2026-01-15T10:00');
    expect(formatTime('2026-07-15T14:00:00Z', 'America/Santiago')).toBe('10:00');
  });
});
