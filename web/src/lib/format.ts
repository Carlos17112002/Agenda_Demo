import type { BookingStatus } from '../api/agenda';

export const WEEKDAYS = [
  'Lunes',
  'Martes',
  'Miércoles',
  'Jueves',
  'Viernes',
  'Sábado',
  'Domingo',
] as const;

export function weekdayLabel(index: number): string {
  return WEEKDAYS[index] ?? '—';
}

export const BOOKING_STATUS_LABELS: Record<BookingStatus, string> = {
  scheduled: 'Agendada',
  confirmed: 'Confirmada',
  completed: 'Completada',
  canceled: 'Cancelada',
  no_show: 'No asistió',
};

const decimal = new Intl.NumberFormat('es-CL', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export function formatMoney(value: string | number | null | undefined): string {
  const numeric = typeof value === 'number' ? value : Number.parseFloat(value ?? '0');
  return `$ ${decimal.format(Number.isFinite(numeric) ? numeric : 0)}`;
}

export function formatPercent(value: string | number | null | undefined): string {
  const numeric = typeof value === 'number' ? value : Number.parseFloat(value ?? '0');
  const formatted = new Intl.NumberFormat('es-CL', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(numeric) ? numeric : 0);
  return `${formatted} %`;
}
