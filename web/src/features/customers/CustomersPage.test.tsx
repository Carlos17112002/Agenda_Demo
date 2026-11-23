import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import type { Customer } from '../../api/customers';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { CustomersPage } from './CustomersPage';

const ana: Customer = {
  id: 'customer-1',
  company: 'company-a',
  first_name: 'Ana',
  last_name: 'Díaz',
  display_name: 'Ana Díaz',
  email: 'ana@example.com',
  phone: '+56911111111',
  document_id: '11111111-1',
  notes: '',
  active: true,
  created_at: '2026-11-01T12:00:00Z',
  updated_at: '2026-11-01T12:00:00Z',
};

const beatriz: Customer = {
  ...ana,
  id: 'customer-2',
  first_name: 'Beatriz',
  last_name: 'Soto',
  display_name: 'Beatriz Soto',
  email: 'beatriz@example.com',
  document_id: '',
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <CustomersPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function listHandler(customers: () => Customer[]) {
  return http.get('http://api.test/api/v1/customers/', () => {
    const results = customers();
    return HttpResponse.json({
      count: results.length,
      next: null,
      previous: null,
      results,
    });
  });
}

describe('CustomersPage', () => {
  test('lista y busca clientes por texto', async () => {
    const urls: string[] = [];
    server.use(
      http.get('http://api.test/api/v1/customers/', ({ request }) => {
        const url = new URL(request.url);
        urls.push(url.toString());
        const search = (url.searchParams.get('search') ?? '').toLowerCase();
        const results = [ana, beatriz].filter((item) =>
          item.display_name.toLowerCase().includes(search),
        );
        return HttpResponse.json({ count: results.length, next: null, previous: null, results });
      }),
    );
    renderPage();

    expect(await screen.findByText(/Ana Díaz/)).toBeInTheDocument();
    expect(screen.getByText('Beatriz Soto')).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('Buscar'), 'beatriz');

    await waitFor(() => expect(screen.queryByText('Ana Díaz')).not.toBeInTheDocument());
    expect(await screen.findByText('Beatriz Soto')).toBeInTheDocument();
    expect(urls.some((url) => url.includes('search=beatriz'))).toBe(true);
  });

  test('crea un cliente con los datos del formulario', async () => {
    let customers = [ana];
    let body: unknown;
    server.use(
      listHandler(() => customers),
      http.post('http://api.test/api/v1/customers/', async ({ request }) => {
        body = await request.json();
        const created: Customer = {
          ...ana,
          id: 'customer-3',
          first_name: 'Carla',
          last_name: 'Muñoz',
          display_name: 'Carla Muñoz',
          email: 'carla@example.com',
          phone: '',
          document_id: '',
        };
        customers = [created, ...customers];
        return HttpResponse.json(created, { status: 201 });
      }),
    );
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo cliente' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Carla');
    await userEvent.type(screen.getByLabelText('Apellido'), 'Muñoz');
    await userEvent.type(screen.getByLabelText('Correo'), 'carla@example.com');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cliente' }));

    await waitFor(() =>
      expect(body).toEqual({
        first_name: 'Carla',
        last_name: 'Muñoz',
        email: 'carla@example.com',
        phone: '',
        document_id: '',
        notes: '',
        active: true,
      }),
    );
    expect(await screen.findByText('Carla Muñoz')).toBeInTheDocument();
  });

  test('muestra el error por campo que devuelve el servidor', async () => {
    server.use(
      listHandler(() => [ana]),
      http.post('http://api.test/api/v1/customers/', () =>
        HttpResponse.json(
          { email: ['Ya existe un cliente con este correo.'] },
          { status: 400 },
        ),
      ),
    );
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo cliente' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Carla');
    await userEvent.type(screen.getByLabelText('Correo'), 'carla@example.com');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cliente' }));

    const dialog = await screen.findByRole('dialog');
    expect(
      await within(dialog).findAllByText('Ya existe un cliente con este correo.'),
    ).not.toHaveLength(0);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  test('desactiva un cliente tras confirmar', async () => {
    let customers = [ana];
    let body: unknown;
    server.use(
      listHandler(() => customers),
      http.patch('http://api.test/api/v1/customers/customer-1/', async ({ request }) => {
        body = await request.json();
        const updated = { ...ana, active: false };
        customers = [updated];
        return HttpResponse.json(updated);
      }),
    );
    renderPage();

    const row = await screen.findByRole('row', { name: /Ana Díaz/ });
    await userEvent.click(within(row).getByRole('button', { name: 'Desactivar' }));
    await userEvent.click(screen.getByRole('button', { name: 'Desactivar' }));

    await waitFor(() => expect(body).toEqual({ active: false }));
    expect(await screen.findByText('Inactivo')).toBeInTheDocument();
  });

  test('devuelve el foco al botón Historial al cerrar', async () => {
    server.use(
      listHandler(() => [ana]),
      http.get('http://api.test/api/v1/bookings/', () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    renderPage();

    const row = await screen.findByRole('row', { name: /Ana Díaz/ });
    const button = within(row).getByRole('button', { name: 'Historial' });
    await userEvent.click(button);
    await screen.findByRole('heading', { name: 'Historial de Ana Díaz' });

    await userEvent.keyboard('{Escape}');

    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: 'Historial de Ana Díaz' })).not.toBeInTheDocument(),
    );
    expect(button).toHaveFocus();
  });

  test('abre el historial de reservas del cliente', async () => {
    const bookingUrls: string[] = [];
    server.use(
      listHandler(() => [ana]),
      http.get('http://api.test/api/v1/bookings/', ({ request }) => {
        bookingUrls.push(request.url);
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
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
            },
          ],
        });
      }),
    );
    renderPage();

    const row = await screen.findByRole('row', { name: /Ana Díaz/ });
    await userEvent.click(within(row).getByRole('button', { name: 'Historial' }));

    expect(
      await screen.findByRole('heading', { name: 'Historial de Ana Díaz' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Corte de cabello')).toBeInTheDocument();
    expect(screen.getByText('Agendada')).toBeInTheDocument();
    expect(bookingUrls[0]).toContain('customer=customer-1');
  });
});
