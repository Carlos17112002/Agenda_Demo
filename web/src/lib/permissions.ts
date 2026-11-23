export function allows(permissions: string[], required: string): boolean {
  if (required === 'bookings.read') {
    return permissions.includes('bookings.read') || permissions.includes('bookings.own.read');
  }
  if (required === 'bookings.write') {
    return permissions.includes('bookings.write') || permissions.includes('bookings.own.write');
  }
  return permissions.includes(required);
}

export type CanFn = (permission: string) => boolean;
export type FeatureFn = (code: string) => boolean;

export type NavItem = {
  path: string;
  label: string;
  permission: string;
  feature?: string;
};

export const NAV_ITEMS: NavItem[] = [
  { path: '/agenda', label: 'Agenda', permission: 'bookings.read', feature: 'bookings' },
  { path: '/clientes', label: 'Clientes', permission: 'customers.read', feature: 'customers' },
  { path: '/servicios', label: 'Servicios', permission: 'catalog.read', feature: 'catalog' },
  { path: '/equipo', label: 'Equipo', permission: 'workforce.read', feature: 'workforce' },
  { path: '/inventario', label: 'Inventario', permission: 'inventory.read', feature: 'inventory' },
  { path: '/resumen', label: 'Resumen', permission: 'reports.read', feature: 'reports' },
  { path: '/usuarios', label: 'Usuarios', permission: 'company.manage' },
  { path: '/marca', label: 'Marca', permission: 'company.manage' },
];

export function visibleNav(can: CanFn, hasFeature: FeatureFn, items: NavItem[] = NAV_ITEMS): NavItem[] {
  return items.filter(
    (item) => can(item.permission) && (item.feature === undefined || hasFeature(item.feature)),
  );
}

export function firstAllowedPath(can: CanFn, hasFeature: FeatureFn): string {
  return visibleNav(can, hasFeature)[0]?.path ?? '/sin-acceso';
}
