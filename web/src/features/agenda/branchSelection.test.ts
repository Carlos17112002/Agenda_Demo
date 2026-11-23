import { describe, expect, test } from 'vitest';

import type { Branch } from '../../api/types';
import { pickInitialBranchId } from './branchSelection';

function branch(id: string, active = true): Branch {
  return {
    id,
    company: 'company-a',
    name: id,
    code: id.toUpperCase(),
    address: '',
    timezone: 'America/Santiago',
    active,
  };
}

describe('pickInitialBranchId', () => {
  test('prefiere el local asignado cuando está activo', () => {
    expect(pickInitialBranchId([branch('a'), branch('b')], 'b')).toBe('b');
  });

  test('usa el primer local activo cuando el asignado está inactivo', () => {
    expect(pickInitialBranchId([branch('a'), branch('b', false)], 'b')).toBe('a');
  });

  test('usa el primer local activo cuando no hay preferencia', () => {
    expect(pickInitialBranchId([branch('a'), branch('b')], null)).toBe('a');
  });

  test('devuelve cadena vacía sin locales', () => {
    expect(pickInitialBranchId([], 'b')).toBe('');
  });
});
