import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { todayInZone } from '../../lib/dates';
import { server } from '../../test/server';
import { makeAuthValue, makeBootstrap } from '../../test/factories';
import { AgendaPage } from './AgendaPage';
import { weekdayIndex } from './agendaLayout';

const bookingFixture = {
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

function renderAgenda(auth = makeAuthValue()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={auth}>
      <QueryClientProvider client={queryClient}>
        <AgendaPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function useAgendaHandlers(bookingUrls: string[] = []) {
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
    http.get('http://api.test/api/v1/bookings/', ({ request }) => {
      bookingUrls.push(request.url);
      return HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [bookingFixture],
      });
    }),
    http.get('http://api.test/api/v1/working-hours/', () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
    http.get('http://api.test/api/v1/customers/', () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
  );
}

describe('AgendaPage', () => {
  test('consulta la agenda de la sucursal y muestra la reserva', async () => {
    const urls: string[] = [];
    useAgendaHandlers(urls);
    renderAgenda();

    expect(await screen.findByText(/Ana Díaz/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Paula Rojas' })).toBeInTheDocument();
    expect(urls[0]).toContain('branch=branch-1');
    expect(urls[0]).toContain('date=');
  });

  test('abre el detalle de la reserva', async () => {
    useAgendaHandlers();
    renderAgenda();

    await userEvent.click(await screen.findByRole('button', { name: /Ana Díaz/ }));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Corte de cabello · Ana Díaz')).toBeInTheDocument();
  });

  test('la vista semanal consulta el rango de lunes a domingo', async () => {
    const urls: string[] = [];
    useAgendaHandlers(urls);
    renderAgenda();
    await screen.findByText(/Ana Díaz/);

    await userEvent.click(screen.getByRole('button', { name: 'Semana' }));

    await waitFor(() => expect(urls.at(-1)).toContain('date_from='));
    expect(urls.at(-1)).toContain('date_to=');
  });

  test('abre el alta con el día, la hora y el trabajador del hueco', async () => {
    useAgendaHandlers();
    const today = todayInZone('America/Santiago');
    server.use(
      http.get('http://api.test/api/v1/working-hours/', () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 'hours-1',
              worker: 'worker-1',
              branch: 'branch-1',
              weekday: weekdayIndex(today),
              start_time: '09:00:00',
              end_time: '18:00:00',
            },
          ],
        }),
      ),
    );
    renderAgenda();
    await screen.findByText(/Ana Díaz/);

    await userEvent.click(
      screen.getByRole('button', { name: /a las 10:00 con Paula Rojas$/ }),
    );

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByLabelText('Día')).toHaveValue(today);
    expect(within(dialog).getByLabelText('Trabajador')).toHaveValue('worker-1');
  });

  test('abre la agenda en el local predeterminado del usuario', async () => {
    const urls: string[] = [];
    useAgendaHandlers(urls);
    const auth = makeAuthValue({
      bootstrap: makeBootstrap({
        membership: {
          id: 'membership-1',
          role: 'owner',
          role_display: 'Propietario',
          default_branch: { id: 'branch-2', name: 'Centro' },
        },
        branches: [
          {
            id: 'branch-1',
            company: 'company-a',
            name: 'Providencia',
            code: 'PROV',
            address: '',
            timezone: 'America/Santiago',
            active: true,
          },
          {
            id: 'branch-2',
            company: 'company-a',
            name: 'Centro',
            code: 'CEN',
            address: '',
            timezone: 'America/Santiago',
            active: true,
          },
        ],
      }),
    });
    renderAgenda(auth);

    await waitFor(() =>
      expect(screen.getByLabelText('Sucursal')).toHaveValue('branch-2'),
    );
    expect(urls[0]).toContain('branch=branch-2');
  });

  test('sin permiso de escritura muestra la grilla sin huecos', async () => {
    useAgendaHandlers();
    renderAgenda(
      makeAuthValue({
        bootstrap: makeBootstrap({
          permissions: ['bookings.read', 'customers.read', 'catalog.read'],
        }),
      }),
    );

    await screen.findByText(/Ana Díaz/);
    expect(screen.getByRole('heading', { name: 'Paula Rojas' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Crear reserva/ })).toBeNull();
  });
});
