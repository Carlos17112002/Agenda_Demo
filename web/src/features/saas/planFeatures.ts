export type PlanFeatureDefinition = {
  code: string;
  label: string;
  shortLabel: string;
  limitLabel?: string;
};

export const PLAN_FEATURES: PlanFeatureDefinition[] = [
  { code: 'bookings', label: 'Agenda y reservas', shortLabel: 'Agenda' },
  { code: 'customers', label: 'Clientes', shortLabel: 'Clientes' },
  { code: 'catalog', label: 'Catálogo de servicios', shortLabel: 'Catálogo' },
  { code: 'workforce', label: 'Trabajadores y horarios', shortLabel: 'Trabajadores y horarios' },
  { code: 'inventory', label: 'Inventario y compras', shortLabel: 'Inventario' },
  { code: 'sales', label: 'Ventas, caja y gastos', shortLabel: 'Ventas' },
  { code: 'reports', label: 'Informes', shortLabel: 'Informes' },
  {
    code: 'branches',
    label: 'Límite de sucursales',
    shortLabel: 'Sucursales',
    limitLabel: 'Máximo de sucursales',
  },
  {
    code: 'workers',
    label: 'Límite de trabajadores',
    shortLabel: 'Trabajadores',
    limitLabel: 'Máximo de trabajadores',
  },
];
