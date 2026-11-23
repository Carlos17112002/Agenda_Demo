import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { useState } from 'react';
import { describe, expect, test } from 'vitest';

import type { Booking } from '../../api/agenda';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { BookingDetailDialog } from './BookingDetailDialog';

const baseBooking: Booking = {
  id: 'booking-1',
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

function Harness({
  initial = baseBooking,
  canWrite = true,
}: {
  initial?: Booking;
  canWrite?: boolean;
}) {
  const [booking, setBooking] = useState<Booking | null>(initial);
  return (
    <BookingDetailDialog
      booking={booking}
      timezone="America/Santiago"
      canWrite={canWrite}
      onClose={() => setBooking(null)}
      onChanged={(updated) => setBooking(updated)}
    />
  );
}

function renderDetail(options: { initial?: Booking; canWrite?: boolean } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <Harness {...options} />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

describe('BookingDetailDialog', () => {
  test('confirma la reserva y refleja el nuevo estado', async () => {
    server.use(
      http.post('http://api.test/api/v1/bookings/booking-1/confirm/', () =>
        HttpResponse.json({ ...baseBooking, status: 'confirmed', status_display: 'Confirmada' }),
      ),
    );
    renderDetail();

    await userEvent.click(screen.getByRole('button', { name: 'Confirmar' }));

    expect(await screen.findByText('Confirmada')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Confirmar' })).not.toBeInTheDocument();
  });

  test('muestra el conflicto al reprogramar', async () => {
    server.use(
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
      http.get('http://api.test/api/v1/bookings/availability/', () =>
        HttpResponse.json({
          date: '2026-11-12',
          timezone: 'America/Santiago',
          slots: [
            { start_at: '2026-11-12T13:30:00Z', end_at: '2026-11-12T14:00:00Z', label: '10:30' },
          ],
        }),
      ),
      http.post('http://api.test/api/v1/bookings/booking-1/reschedule/', () =>
        HttpResponse.json(
          { detail: 'El horario seleccionado ya no está disponible.' },
          { status: 409 },
        ),
      ),
    );
    renderDetail();

    await userEvent.click(screen.getByRole('button', { name: 'Reprogramar' }));
    await userEvent.click(await screen.findByRole('button', { name: '10:30' }));
    await userEvent.click(screen.getByRole('button', { name: 'Reprogramar reserva' }));

    expect(
      await screen.findByText('El horario seleccionado ya no está disponible.'),
    ).toBeInTheDocument();
  });

  test('guarda las notas con PATCH', async () => {
    let body: unknown;
    server.use(
      http.patch('http://api.test/api/v1/bookings/booking-1/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...baseBooking, notes: 'Llegó antes' });
      }),
    );
    renderDetail();

    await userEvent.type(screen.getByLabelText('Notas'), 'Llegó antes');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar notas' }));

    await waitFor(() => expect(body).toEqual({ notes: 'Llegó antes' }));
  });

  test('sin permiso de escritura no muestra acciones', () => {
    renderDetail({ canWrite: false });
    expect(screen.queryByRole('button', { name: 'Confirmar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reprogramar' })).not.toBeInTheDocument();
  });

  test('devuelve el foco al disparador al cerrar', async () => {
    function FocusHarness() {
      const [booking, setBooking] = useState<Booking | null>(null);
      return (
        <>
          <button type="button" onClick={() => setBooking(baseBooking)}>
            Abrir detalle
          </button>
          <BookingDetailDialog
            booking={booking}
            timezone="America/Santiago"
            canWrite
            onClose={() => setBooking(null)}
            onChanged={setBooking}
          />
        </>
      );
    }
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <AuthContext.Provider value={makeAuthValue()}>
        <QueryClientProvider client={queryClient}>
          <FocusHarness />
        </QueryClientProvider>
      </AuthContext.Provider>,
    );

    const trigger = screen.getByRole('button', { name: 'Abrir detalle' });
    await userEvent.click(trigger);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await userEvent.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
