import { describe, expect, test } from 'vitest';

import { allows, firstAllowedPath, visibleNav } from './permissions';

describe('permisos', () => {
  test('la agenda acepta el permiso propio del trabajador', () => {
    expect(allows(['bookings.own.read'], 'bookings.read')).toBe(true);
    expect(allows(['bookings.own.write'], 'bookings.write')).toBe(true);
    expect(allows(['bookings.own.read'], 'bookings.write')).toBe(false);
  });

  test('oculta secciones sin permiso o sin funcionalidad', () => {
    const can = (permission: string) => permission !== 'reports.read';
    const hasFeature = (code: string) => code !== 'workforce';
    const paths = visibleNav(can, hasFeature).map((item) => item.path);
    expect(paths).toEqual(['/agenda', '/clientes', '/servicios', '/inventario', '/usuarios', '/marca']);
  });

  test('sin secciones permitidas devuelve la pantalla de acceso restringido', () => {
    expect(firstAllowedPath(() => false, () => true)).toBe('/sin-acceso');
  });
});
