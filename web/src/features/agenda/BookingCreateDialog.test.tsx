import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test, vi } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { BookingCreateDialog } from './BookingCreateDialog';
import type { CalendarSlot } from './agendaLayout';

const bookingFixture = {
  id: 'booking-9',
  company: 'company-a',
  branch: 'branch-1',
  branch_name: 'Providencia',
  customer: 'customer-1',
  customer_name: 'Ana Díaz',
  customer_email: 'ana@example.com',
  service: 'service-1',
  service_name: 'Corte de cabello',
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

const baseHandlers = [
  http.get('http://api.test/api/v1/services/', () =>
    HttpResponse.json({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 'service-1',
          company: 'company-a',
          name: 'Corte de cabello',
          description: '',
          duration_minutes: 30,
          price: '12000.00',
          buffer_before_minutes: 0,
          buffer_after_minutes: 0,
          branches: ['branch-1'],
          active: true,
          created_at: '2026-11-11T12:00:00Z',
          updated_at: '2026-11-11T12:00:00Z',
        },
      ],
    }),
  ),
  http.get('http://api.test/api/v1/workers/', () =>
    HttpResponse.json({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 'worker-1',
          company: 'company-a',
          membership: null,
          first_name: 'Paula',
          last_name: 'Rojas',
          display_name: 'Paula Rojas',
          email: '',
          phone: '',
          job_title: 'Estilista',
          color: '#10b981',
          branches: ['branch-1'],
          active: true,
          created_at: '2026-11-11T12:00:00Z',
          updated_at: '2026-11-11T12:00:00Z',
        },
      ],
    }),
  ),
  http.get('http://api.test/api/v1/customers/', () =>
    HttpResponse.json({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 'customer-1',
          company: 'company-a',
          first_name: 'Ana',
          last_name: 'Díaz',
          display_name: 'Ana Díaz',
          email: 'ana@example.com',
          phone: '',
          document_id: '',
          notes: '',
          active: true,
          created_at: '2026-11-11T12:00:00Z',
          updated_at: '2026-11-11T12:00:00Z',
        },
      ],
    }),
  ),
  http.get('http://api.test/api/v1/bookings/availability/', () =>
    HttpResponse.json({
      date: '2026-11-12',
      timezone: 'America/Santiago',
      slots: [
        { start_at: '2026-11-12T13:00:00Z', end_at: '2026-11-12T13:30:00Z', label: '10:00' },
        { start_at: '2026-11-12T13:30:00Z', end_at: '2026-11-12T14:00:00Z', label: '10:30' },
      ],
    }),
  ),
];

function renderDialog(open = true, initialSlot: CalendarSlot | null = null) {
  const onCreated = vi.fn();
  const onOpenChange = vi.fn();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <BookingCreateDialog
          open={open}
          onOpenChange={onOpenChange}
          defaultBranchId="branch-1"
          defaultDate="2026-11-12"
          initialSlot={initialSlot}
          onCreated={onCreated}
        />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
  return { onCreated, onOpenChange, queryClient };
}

async function chooseServiceWorkerAndSlot() {
  await screen.findByRole('option', { name: 'Corte de cabello · 30 min' });
  await userEvent.selectOptions(screen.getByLabelText('Servicio'), 'service-1');
  await screen.findByRole('option', { name: 'Paula Rojas' });
  await userEvent.selectOptions(screen.getByLabelText('Trabajador'), 'worker-1');
  await userEvent.click(await screen.findByRole('button', { name: '10:00' }));
}

describe('BookingCreateDialog', () => {
  test('crea la reserva con un cliente existente y un cupo disponible', async () => {
    let created: unknown;
    server.use(
      ...baseHandlers,
      http.post('http://api.test/api/v1/bookings/', async ({ request }) => {
        created = await request.json();
        return HttpResponse.json(bookingFixture, { status: 201 });
      }),
    );
    const { onCreated, onOpenChange } = renderDialog();

    await chooseServiceWorkerAndSlot();
    await screen.findByRole('option', { name: /Ana Díaz/ });
    await userEvent.selectOptions(screen.getByLabelText('Cliente'), 'customer-1');
    await userEvent.click(screen.getByRole('button', { name: 'Crear reserva' }));

    await waitFor(() =>
      expect(created).toMatchObject({
        branch: 'branch-1',
        service: 'service-1',
        worker: 'worker-1',
        customer: 'customer-1',
        start_at: '2026-11-12T13:00:00Z',
      }),
    );
    expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: 'booking-9' }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  test('un 409 conserva el diálogo y muestra el mensaje del servidor', async () => {
    server.use(
      ...baseHandlers,
      http.post('http://api.test/api/v1/bookings/', () =>
        HttpResponse.json(
          { detail: 'El horario seleccionado ya no está disponible.' },
          { status: 409 },
        ),
      ),
    );
    const { onCreated, onOpenChange } = renderDialog();

    await chooseServiceWorkerAndSlot();
    await screen.findByRole('option', { name: /Ana Díaz/ });
    await userEvent.selectOptions(screen.getByLabelText('Cliente'), 'customer-1');
    await userEvent.click(screen.getByRole('button', { name: 'Crear reserva' }));

    expect(
      await screen.findByText('El horario seleccionado ya no está disponible.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  test('crea un cliente nuevo antes de la reserva', async () => {
    const calls: string[] = [];
    let bookingBody: unknown;
    server.use(
      ...baseHandlers,
      http.post('http://api.test/api/v1/customers/', async ({ request }) => {
        calls.push('customer');
        const body = await request.json();
        return HttpResponse.json({ id: 'customer-new', ...(body as object) }, { status: 201 });
      }),
      http.post('http://api.test/api/v1/bookings/', async ({ request }) => {
        calls.push('booking');
        bookingBody = await request.json();
        return HttpResponse.json({ ...bookingFixture, customer: 'customer-new' }, { status: 201 });
      }),
    );
    renderDialog();

    await chooseServiceWorkerAndSlot();
    await userEvent.click(screen.getByRole('button', { name: 'Nuevo cliente' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Carla');
    await userEvent.type(screen.getByLabelText('Correo del cliente'), 'carla@example.com');
    await userEvent.click(screen.getByRole('button', { name: 'Crear reserva' }));

    await waitFor(() => expect(calls).toEqual(['customer', 'booking']));
    expect(bookingBody).toMatchObject({ customer: 'customer-new' });
  });

  test('preselecciona el horario y el trabajador solicitados', async () => {
    server.use(...baseHandlers);
    renderDialog(true, { date: '2026-11-12', time: '10:30', workerId: 'worker-1' });

    await screen.findByRole('option', { name: 'Paula Rojas' });
    expect(screen.getByLabelText('Trabajador')).toHaveValue('worker-1');
    await userEvent.selectOptions(screen.getByLabelText('Servicio'), 'service-1');

    const slot = await screen.findByRole('button', { name: '10:30' });
    await waitFor(() => expect(slot).toHaveAttribute('aria-pressed', 'true'));
  });
});
