import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import { server } from '../test/server';
import { createAgendaApi } from './agenda';
import { createBrandingApi } from './branding';
import { ApiClient } from './client';
import { createCustomersApi } from './customers';
import { createServicesApi } from './services';
import { createSummaryApi } from './summary';
import { createTeamApi } from './team';

function makeClient() {
  return new ApiClient({
    baseUrl: 'http://api.test',
    getAccessToken: () => 'access-1',
    getTenantContextId: () => 'ctx-1',
  });
}

const bookingFixture = {
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
  start_at: '2026-11-12T13:00:00Z',
  end_at: '2026-11-12T13:30:00Z',
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
};

describe('agendaApi', () => {
  test('crea la reserva con el inicio en UTC y consulta disponibilidad', async () => {
    let createBody: unknown;
    let availabilityUrl = '';
    server.use(
      http.get('http://api.test/api/v1/bookings/availability/', ({ request }) => {
        availabilityUrl = request.url;
        return HttpResponse.json({
          date: '2026-11-12',
          timezone: 'America/Santiago',
          slots: [
            { start_at: '2026-11-12T13:00:00Z', end_at: '2026-11-12T13:30:00Z', label: '10:00' },
          ],
        });
      }),
      http.post('http://api.test/api/v1/bookings/', async ({ request }) => {
        createBody = await request.json();
        return HttpResponse.json(bookingFixture, { status: 201 });
      }),
    );

    const api = createAgendaApi(makeClient());
    const availability = await api.availability({
      branch: 'branch-1',
      service: 'service-1',
      worker: 'worker-1',
      date: '2026-11-12',
    });
    const booking = await api.createBooking({
      branch: 'branch-1',
      customer: 'customer-1',
      service: 'service-1',
      worker: 'worker-1',
      start_at: availability.slots[0].start_at,
      notes: 'Primera visita',
    });

    expect(availabilityUrl).toContain('date=2026-11-12');
    expect(createBody).toMatchObject({
      branch: 'branch-1',
      customer: 'customer-1',
      service: 'service-1',
      worker: 'worker-1',
      start_at: '2026-11-12T13:00:00Z',
      notes: 'Primera visita',
    });
    expect(booking.id).toBe('booking-1');
  });

  test('usa la acción dedicada para reprogramar y cambiar de estado', async () => {
    const calls: string[] = [];
    server.use(
      http.post('http://api.test/api/v1/bookings/booking-1/reschedule/', () => {
        calls.push('reschedule');
        return HttpResponse.json({ ...bookingFixture, start_at: '2026-11-13T14:00:00Z' });
      }),
      http.post('http://api.test/api/v1/bookings/booking-1/confirm/', () => {
        calls.push('confirm');
        return HttpResponse.json({ ...bookingFixture, status: 'confirmed' });
      }),
      http.patch('http://api.test/api/v1/bookings/booking-1/', async ({ request }) => {
        calls.push('notes');
        expect(await request.json()).toEqual({ notes: 'Llegó antes' });
        return HttpResponse.json({ ...bookingFixture, notes: 'Llegó antes' });
      }),
    );

    const api = createAgendaApi(makeClient());
    await api.rescheduleBooking('booking-1', { start_at: '2026-11-13T14:00:00Z' });
    await api.transitionBooking('booking-1', 'confirm');
    await api.updateNotes('booking-1', 'Llegó antes');

    expect(calls).toEqual(['reschedule', 'confirm', 'notes']);
  });
});

describe('customersApi', () => {
  test('busca, crea y desactiva clientes', async () => {
    let listUrl = '';
    let created: unknown;
    let deactivated: unknown;
    server.use(
      http.get('http://api.test/api/v1/customers/', ({ request }) => {
        listUrl = request.url;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
      http.post('http://api.test/api/v1/customers/', async ({ request }) => {
        created = await request.json();
        return HttpResponse.json({ id: 'customer-2', ...(created as object) }, { status: 201 });
      }),
      http.patch('http://api.test/api/v1/customers/customer-2/', async ({ request }) => {
        deactivated = await request.json();
        return HttpResponse.json({ id: 'customer-2', active: false });
      }),
    );

    const api = createCustomersApi(makeClient());
    await api.list({ search: 'ana', active: true });
    await api.create({ first_name: 'Ana', email: 'ana@example.com' });
    await api.setActive('customer-2', false);

    expect(listUrl).toContain('search=ana');
    expect(listUrl).toContain('active=true');
    expect(created).toMatchObject({ first_name: 'Ana', email: 'ana@example.com' });
    expect(deactivated).toEqual({ active: false });
  });
});

describe('servicesApi', () => {
  test('envía duración, buffers y sucursales del servicio', async () => {
    let body: unknown;
    server.use(
      http.post('http://api.test/api/v1/services/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: 'service-1', ...(body as object) }, { status: 201 });
      }),
    );

    await createServicesApi(makeClient()).create({
      name: 'Corte',
      description: '',
      duration_minutes: 45,
      price: '12000.00',
      buffer_before_minutes: 5,
      buffer_after_minutes: 10,
      branches: ['branch-1'],
      active: true,
    });

    expect(body).toMatchObject({
      duration_minutes: 45,
      buffer_before_minutes: 5,
      buffer_after_minutes: 10,
      branches: ['branch-1'],
    });
  });
});

describe('teamApi', () => {
  test('crea horario, pausa, ausencia y bloqueo con sus campos', async () => {
    const bodies: Record<string, unknown> = {};
    server.use(
      http.post('http://api.test/api/v1/working-hours/', async ({ request }) => {
        bodies.hours = await request.json();
        return HttpResponse.json({ id: 'hours-1' }, { status: 201 });
      }),
      http.post('http://api.test/api/v1/breaks/', async ({ request }) => {
        bodies.break = await request.json();
        return HttpResponse.json({ id: 'break-1' }, { status: 201 });
      }),
      http.post('http://api.test/api/v1/time-off/', async ({ request }) => {
        bodies.timeOff = await request.json();
        return HttpResponse.json({ id: 'timeoff-1' }, { status: 201 });
      }),
      http.post('http://api.test/api/v1/blocked-slots/', async ({ request }) => {
        bodies.blocked = await request.json();
        return HttpResponse.json({ id: 'blocked-1' }, { status: 201 });
      }),
      http.delete(
        'http://api.test/api/v1/working-hours/hours-1/',
        () => new HttpResponse(null, { status: 204 }),
      ),
    );

    const api = createTeamApi(makeClient());
    await api.workingHours.create({
      worker: 'worker-1',
      branch: 'branch-1',
      weekday: 0,
      start_time: '09:00',
      end_time: '13:00',
    });
    await api.breaks.create({
      worker: 'worker-1',
      branch: 'branch-1',
      weekday: 0,
      start_time: '11:00',
      end_time: '11:15',
      label: 'Pausa',
    });
    await api.timeOff.create({
      worker: 'worker-1',
      branch: 'branch-1',
      starts_at: '2026-11-20T13:00:00Z',
      ends_at: '2026-11-20T21:00:00Z',
      reason: 'Vacaciones',
    });
    await api.blockedSlots.create({
      worker: 'worker-1',
      branch: null,
      starts_at: '2026-11-21T13:00:00Z',
      ends_at: '2026-11-21T15:00:00Z',
      reason: 'Trámite',
    });
    await expect(api.workingHours.remove('hours-1')).resolves.toBeUndefined();

    expect(bodies.hours).toMatchObject({ weekday: 0, start_time: '09:00', end_time: '13:00' });
    expect(bodies.break).toMatchObject({ label: 'Pausa' });
    expect(bodies.timeOff).toMatchObject({ reason: 'Vacaciones' });
    expect(bodies.blocked).toMatchObject({ branch: null });
  });
});

describe('summaryApi', () => {
  test('envía rango y sucursal a ambos informes', async () => {
    const urls: string[] = [];
    server.use(
      http.get('http://api.test/api/v1/reports/sales-summary/', ({ request }) => {
        urls.push(request.url);
        return HttpResponse.json({ totals: {} });
      }),
      http.get('http://api.test/api/v1/reports/cash-summary/', ({ request }) => {
        urls.push(request.url);
        return HttpResponse.json({ totals: {} });
      }),
    );

    const api = createSummaryApi(makeClient());
    await api.sales({ date_from: '2026-11-05', date_to: '2026-11-11', branch: 'branch-1' });
    await api.cash({ date_from: '2026-11-05', date_to: '2026-11-11', branch: 'branch-1' });

    expect(urls).toHaveLength(2);
    urls.forEach((url) => {
      expect(url).toContain('date_from=2026-11-05');
      expect(url).toContain('date_to=2026-11-11');
      expect(url).toContain('branch=branch-1');
    });
  });
});

describe('brandingApi', () => {
  test('actualiza la marca y sube el logo como multipart', async () => {
    let patchBody: unknown;
    server.use(
      http.patch('http://api.test/api/v1/company/branding/', async ({ request }) => {
        patchBody = await request.json();
        return HttpResponse.json({ display_name: 'Aurora', slug: 'aurora' });
      }),
    );

    // Node 24's fetch no reconoce el FormData de jsdom (otro realm), así que se
    // captura el cuerpo antes de enviarlo; el multipart real se cubre en el E2E.
    const captured: { method?: string; body?: FormData } = {};
    const uploadClient = new ApiClient({
      baseUrl: 'http://api.test',
      getAccessToken: () => 'access-1',
      getTenantContextId: () => 'ctx-1',
      fetchImpl: async (_input, init) => {
        captured.method = init?.method;
        captured.body = init?.body as FormData;
        return new Response(
          JSON.stringify({ display_name: 'Aurora', logo_url: '/media/logo.png' }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      },
    });

    const api = createBrandingApi(makeClient());
    await api.update({ display_name: 'Aurora', theme_mode: 'dark' });
    const file = new File(['png'], 'logo.png', { type: 'image/png' });
    await createBrandingApi(uploadClient).uploadLogo(file);

    expect(patchBody).toEqual({ display_name: 'Aurora', theme_mode: 'dark' });
    expect(captured.method).toBe('POST');
    expect((captured.body?.get('logo') as File).name).toBe('logo.png');
  });

  test('propaga el error por campo del servidor', async () => {
    server.use(
      http.patch('http://api.test/api/v1/company/branding/', () =>
        HttpResponse.json(
          { slug: ['Este identificador de empresa ya está ocupado.'] },
          { status: 400 },
        ),
      ),
    );

    await expect(createBrandingApi(makeClient()).update({ slug: 'ocupado' })).rejects.toMatchObject({
      status: 400,
      fields: { slug: ['Este identificador de empresa ya está ocupado.'] },
    });
  });
});
