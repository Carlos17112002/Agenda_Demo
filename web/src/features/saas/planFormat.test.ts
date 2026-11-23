import { describe, expect, test } from 'vitest';

import { featureSummary, formatAmount } from './planFormat';

describe('planFormat', () => {
  test('formatea el precio en es-CL con la moneda del plan', () => {
    expect(formatAmount({ price: '19990.00', currency: 'CLP' })).toBe('CLP 19.990');
  });

  test('resume funcionalidades activas con sus límites', () => {
    expect(featureSummary({
      price: '0', currency: 'CLP',
      features: [
        { code: 'sales', enabled: true, limit_value: null },
        { code: 'branches', enabled: true, limit_value: 5 },
        { code: 'inventory', enabled: false, limit_value: null },
      ],
    })).toBe('Ventas · Sucursales: 5');
  });

  test('devuelve un guion cuando no hay funcionalidades activas', () => {
    expect(featureSummary({ price: '0', currency: 'CLP', features: [] })).toBe('—');
  });
});
