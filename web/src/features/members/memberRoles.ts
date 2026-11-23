import type { MemberRole } from '../../api/members';

export const MEMBER_ROLES: { value: MemberRole; label: string }[] = [
  { value: 'owner', label: 'Propietario' },
  { value: 'admin', label: 'Administrador' },
  { value: 'manager', label: 'Supervisor' },
  { value: 'reception', label: 'Recepción' },
  { value: 'worker', label: 'Trabajador' },
  { value: 'inventory', label: 'Inventario' },
  { value: 'accounting', label: 'Contabilidad' },
];

export function roleLabel(role: string): string {
  return MEMBER_ROLES.find((item) => item.value === role)?.label ?? role;
}
