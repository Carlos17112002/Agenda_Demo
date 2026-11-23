const LABELS: Record<string, string> = {
  'bookings.read': 'Ver reservas',
  'bookings.write': 'Gestionar reservas',
  'bookings.own.read': 'Ver sus reservas',
  'bookings.own.write': 'Gestionar sus reservas',
  'customers.read': 'Ver clientes',
  'customers.write': 'Gestionar clientes',
  'customers.assigned.read': 'Ver clientes asignados',
  'catalog.read': 'Ver servicios',
  'catalog.write': 'Gestionar servicios',
  'workforce.read': 'Ver equipo',
  'workforce.write': 'Gestionar equipo',
  'inventory.read': 'Ver inventario',
  'inventory.write': 'Gestionar inventario',
  'purchases.read': 'Ver compras',
  'purchases.write': 'Gestionar compras',
  'sales.read': 'Ver ventas',
  'sales.write': 'Gestionar ventas',
  'cash.read': 'Ver caja',
  'cash.manage': 'Gestionar caja',
  'payments.read': 'Ver pagos',
  'expenses.read': 'Ver gastos',
  'expenses.write': 'Gestionar gastos',
  'reports.read': 'Ver reportes',
  'subscription.read': 'Ver suscripción',
  'subscription.manage': 'Gestionar suscripción',
  'branches.read': 'Ver locales',
  'branches.manage': 'Gestionar locales',
  'company.manage': 'Administrar empresa',
};

const GROUPS: Record<string, string> = {
  bookings: 'Reservas',
  customers: 'Clientes',
  catalog: 'Servicios',
  workforce: 'Equipo',
  inventory: 'Inventario',
  purchases: 'Compras',
  sales: 'Ventas',
  cash: 'Caja',
  payments: 'Pagos',
  expenses: 'Gastos',
  reports: 'Reportes',
  subscription: 'Suscripción',
  branches: 'Locales',
  company: 'Empresa',
};

export function permissionLabel(code: string): string {
  return LABELS[code] ?? code;
}

export function permissionGroup(code: string): string {
  return GROUPS[code.split('.')[0]] ?? 'Otros';
}
