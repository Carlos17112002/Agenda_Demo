import { describe, expect, test } from 'vitest';

import type { Booking } from '../../api/agenda';
import type { WorkingHours } from '../../api/team';
import {
  bookingBlockStyle,
  groupWeek,
  hourBounds,
  overlapLanes,
  slotBlockStyle,
  slotStarts,
  slotStepMinutes,
  timeLabel,
  weekdayIndex,
} from './agendaLayout';

const booking = (overrides: Partial<Booking> = {}): Booking => ({
  id: 'booking-1',
  company: 'company-a',
  branch: 'branch-1',
  branch_name: 'Providencia',
  customer: 'customer-1',
  customer_name: 'Ana Díaz',
  customer_email: 'ana@example.com',
  service: 'service-1',
  service_name: 'Corte',
  worker: 'worker-1',
  worker_name: 'Paula Rojas',
  start_at: '2026-01-15T13:00:00Z',
  end_at: '2026-01-15T13:30:00Z',
  duration_minutes: 30,
  price: '12000.00',
  status: 'scheduled',
  status_display: 'Agendada',
  source: 'staff',
  source_display: 'Equipo',
  notes: '',
  public_code: 'ABCDEFGHIJ',
  canceled_at: null,
  canceled_reason: '',
  created_at: '2026-11-11T12:00:00Z',
  updated_at: '2026-11-11T12:00:00Z',
  ...overrides,
});

describe('agendaLayout', () => {
  test('amplía el eje cuando hay reservas fuera del horario por defecto', () => {
    expect(hourBounds([], 'America/Santiago')).toEqual({ startHour: 8, endHour: 20 });
    const early = booking({ start_at: '2026-01-15T10:00:00Z', end_at: '2026-01-15T10:30:00Z' });
    const late = booking({ id: 'b2', start_at: '2026-01-15T23:30:00Z', end_at: '2026-01-16T00:00:00Z' });
    expect(hourBounds([early, late], 'America/Santiago')).toEqual({ startHour: 7, endHour: 21 });
  });

  test('posiciona el bloque según la hora local de la sucursal', () => {
    const style = bookingBlockStyle(booking(), 8, 20, 'America/Santiago');
    expect(Number.parseFloat(style.top)).toBeCloseTo(16.67, 2);
    expect(Number.parseFloat(style.height)).toBeCloseTo(4.17, 2);
  });

  test('agrupa la semana por fecha local', () => {
    const nextDay = booking({
      id: 'booking-2',
      start_at: '2026-01-16T13:00:00Z',
      end_at: '2026-01-16T13:30:00Z',
    });
    const week = groupWeek([booking(), nextDay], '2026-01-12', 'America/Santiago');
    expect(week).toHaveLength(7);
    expect(week[3].bookings.map((item) => item.id)).toEqual(['booking-1']);
    expect(week[4].bookings.map((item) => item.id)).toEqual(['booking-2']);
  });

  test('usa el horario de atención de la sucursal cuando existe', () => {
    const shift: WorkingHours = {
      id: 'hours-1',
      worker: 'worker-1',
      branch: 'branch-1',
      weekday: 0,
      start_time: '09:00:00',
      end_time: '18:00:00',
    };
    expect(hourBounds([], 'America/Santiago', [shift], [0])).toEqual({
      startHour: 9,
      endHour: 18,
    });
  });

  test('ignora los turnos de días que no están a la vista', () => {
    const shift: WorkingHours = {
      id: 'hours-1',
      worker: 'worker-1',
      branch: 'branch-1',
      weekday: 0,
      start_time: '09:00:00',
      end_time: '18:00:00',
    };
    expect(hourBounds([], 'America/Santiago', [shift], [5])).toEqual({
      startHour: 8,
      endHour: 20,
    });
  });

  test('interpreta el fin a medianoche como 24:00', () => {
    const shift: WorkingHours = {
      id: 'hours-1',
      worker: 'worker-1',
      branch: 'branch-1',
      weekday: 0,
      start_time: '18:00:00',
      end_time: '00:00:00',
    };
    expect(hourBounds([], 'America/Santiago', [shift], [0])).toEqual({
      startHour: 18,
      endHour: 24,
    });
  });

  test('amplía el eje por reservas fuera del horario de atención', () => {
    const early = booking({
      start_at: '2026-01-15T10:00:00Z',
      end_at: '2026-01-15T10:30:00Z',
    });
    const shift: WorkingHours = {
      id: 'hours-1',
      worker: 'worker-1',
      branch: 'branch-1',
      weekday: 3,
      start_time: '09:00:00',
      end_time: '18:00:00',
    };
    expect(hourBounds([early], 'America/Santiago', [shift], [3])).toEqual({
      startHour: 7,
      endHour: 18,
    });
  });

  test('calcula días, franjas y etiquetas del calendario', () => {
    expect(weekdayIndex('2026-01-12')).toBe(0);
    expect(weekdayIndex('2026-01-18')).toBe(6);
    expect(slotStepMinutes(8, 20)).toBe(30);
    expect(slotStepMinutes(0, 24)).toBe(60);
    expect(slotStarts(9, 10)).toEqual([540, 570]);
    expect(timeLabel(570)).toBe('09:30');
    expect(slotBlockStyle(570, 9, 10)).toEqual({ top: '50%', height: '50%' });
  });

  test('reparte reservas solapadas en carriles', () => {
    const first = booking({
      id: 'b1',
      start_at: '2026-01-15T13:00:00Z',
      end_at: '2026-01-15T14:00:00Z',
      duration_minutes: 60,
    });
    const overlap = booking({
      id: 'b2',
      start_at: '2026-01-15T13:30:00Z',
      end_at: '2026-01-15T14:30:00Z',
      duration_minutes: 60,
    });
    const later = booking({
      id: 'b3',
      start_at: '2026-01-15T15:00:00Z',
      end_at: '2026-01-15T15:30:00Z',
      duration_minutes: 30,
    });
    const layout = overlapLanes([first, overlap, later], 'America/Santiago');
    expect(layout.lanes).toBe(2);
    expect(layout.laneOf.get('b1')).toBe(0);
    expect(layout.laneOf.get('b2')).toBe(1);
    expect(layout.laneOf.get('b3')).toBe(0);
  });
});
