import type { Branch, E2ESession } from './api';
import { apiCall } from './api';

type Paginated<T> = { results: T[] };

export type Seed = {
  branch: Branch;
  service: { id: string; name: string };
  worker: { id: string; display_name: string };
  customer: { id: string; display_name: string };
  date: string;
  booking?: { id: string };
};

export const BOOKING_OFFSET_DAYS = 3;

export function uniqueSuffix(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

async function list<T>(session: E2ESession, path: string): Promise<T[]> {
  const data = await apiCall<Paginated<T> | T[]>(path, {
    token: session.access,
    contextId: session.contextId,
  });
  return Array.isArray(data) ? data : data.results;
}

export function dateInZone(timeZone: string, offsetDays: number): string {
  const formatted = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
  const [year, month, day] = formatted.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, day + offsetDays)).toISOString().slice(0, 10);
}

export function weekdayIndex(date: string): number {
  const [year, month, day] = date.split('-').map(Number);
  return (new Date(Date.UTC(year, month - 1, day)).getUTCDay() + 6) % 7;
}

export async function seedCompany(
  session: E2ESession,
  suffix: string,
  options: { withBooking?: boolean } = {},
): Promise<Seed> {
  const auth = { token: session.access, contextId: session.contextId };
  const branches = await list<Branch>(session, '/api/v1/branches/?active=true&page=1');
  const branch =
    branches[0] ??
    (await apiCall<Branch>('/api/v1/branches/', {
      ...auth,
      method: 'POST',
      body: {
        name: `Sucursal ${suffix}`,
        code: `E${suffix.slice(-6)}`.toUpperCase(),
        timezone: 'America/Santiago',
        active: true,
      },
    }));

  const service = await apiCall<Seed['service']>('/api/v1/services/', {
    ...auth,
    method: 'POST',
    body: {
      name: `Servicio ${suffix}`,
      description: 'Datos de prueba E2E',
      duration_minutes: 30,
      price: '15000.00',
      buffer_before_minutes: 0,
      buffer_after_minutes: 0,
      branches: [branch.id],
      active: true,
    },
  });

  const worker = await apiCall<Seed['worker']>('/api/v1/workers/', {
    ...auth,
    method: 'POST',
    body: {
      first_name: 'Trabajador',
      last_name: suffix,
      job_title: 'E2E',
      color: '#2563EB',
      branches: [branch.id],
      active: true,
    },
  });

  for (let weekday = 0; weekday < 7; weekday += 1) {
    await apiCall('/api/v1/working-hours/', {
      ...auth,
      method: 'POST',
      body: {
        worker: worker.id,
        branch: branch.id,
        weekday,
        start_time: '08:00:00',
        end_time: '20:00:00',
      },
    });
  }

  const customer = await apiCall<Seed['customer']>('/api/v1/customers/', {
    ...auth,
    method: 'POST',
    body: {
      first_name: 'Cliente',
      last_name: suffix,
      email: `e2e-${suffix}@example.com`,
      phone: '+56911112222',
    },
  });

  const date = dateInZone(branch.timezone, BOOKING_OFFSET_DAYS);
  let booking: Seed['booking'];

  if (options.withBooking) {
    const availability = await apiCall<{ slots: { start_at: string }[] }>(
      `/api/v1/bookings/availability/?branch=${branch.id}&service=${service.id}` +
        `&worker=${worker.id}&date=${date}`,
      auth,
    );
    const slot = availability.slots[0];
    if (!slot) throw new Error('El trabajador E2E no tiene cupos en la fecha elegida.');

    booking = await apiCall<{ id: string }>('/api/v1/bookings/', {
      ...auth,
      method: 'POST',
      body: {
        branch: branch.id,
        customer: customer.id,
        service: service.id,
        worker: worker.id,
        start_at: slot.start_at,
        notes: 'Reserva E2E',
      },
    });
  }

  return { branch, service, worker, customer, date, booking };
}
