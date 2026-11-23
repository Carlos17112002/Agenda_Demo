import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import type { Service } from '../../api/services';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { ServicesPage } from './ServicesPage';

const corte: Service = {
  id: 'service-1',
  company: 'company-a',
  name: 'Corte de cabello',
  description: 'Corte clásico',
  duration_minutes: 30,
  price: '12000.00',
  buffer_before_minutes: 0,
  buffer_after_minutes: 10,
  branches: ['branch-1'],
  active: true,
  created_at: '2026-11-01T12:00:00Z',
  updated_at: '2026-11-01T12:00:00Z',
};

const color: Service = {
  ...corte,
  id: 'service-2',
  name: 'Color completo',
  duration_minutes: 90,
  price: '35000.00',
  branches: [],
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <ServicesPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function listHandler(services: () => Service[]) {
  return http.get('http://api.test/api/v1/services/', () => {
    const results = services();
    return HttpResponse.json({
      count: results.length,
      next: null,
      previous: null,
      results,
    });
  });
}

describe('ServicesPage', () => {
  test('lista servicios con duración, precio y sucursales', async () => {
    server.use(listHandler(() => [corte, color]));
    renderPage();

    const row = await screen.findByRole('row', { name: /Corte de cabello/ });
    expect(within(row).getByText('30 min')).toBeInTheDocument();
    expect(within(row).getByText('$ 12.000')).toBeInTheDocument();
    expect(within(row).getByText('Providencia')).toBeInTheDocument();
    expect(screen.getByText('Todas las sucursales')).toBeInTheDocument();
  });

  test('crea un servicio con sucursal y valores numéricos', async () => {
    let services = [corte];
    let body: unknown;
    server.use(
      listHandler(() => services),
      http.post('http://api.test/api/v1/services/', async ({ request }) => {
        body = await request.json();
        const created: Service = {
          ...corte,
          id: 'service-3',
          name: 'Corte premium',
          description: '',
          duration_minutes: 45,
          price: '15000',
          buffer_after_minutes: 0,
        };
        services = [...services, created];
        return HttpResponse.json(created, { status: 201 });
      }),
    );
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo servicio' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Corte premium');
    await userEvent.clear(screen.getByLabelText('Duración (minutos)'));
    await userEvent.type(screen.getByLabelText('Duración (minutos)'), '45');
    await userEvent.clear(screen.getByLabelText('Precio'));
    await userEvent.type(screen.getByLabelText('Precio'), '15000');
    await userEvent.click(screen.getByRole('checkbox', { name: 'Providencia' }));
    await userEvent.click(screen.getByRole('button', { name: 'Guardar servicio' }));

    await waitFor(() =>
      expect(body).toEqual({
        name: 'Corte premium',
        description: '',
        duration_minutes: 45,
        price: '15000',
        buffer_before_minutes: 0,
        buffer_after_minutes: 0,
        branches: ['branch-1'],
        active: true,
      }),
    );
    expect(await screen.findByText('Corte premium')).toBeInTheDocument();
  });

  test('muestra el nombre duplicado que rechaza el servidor', async () => {
    server.use(
      listHandler(() => [corte]),
      http.post('http://api.test/api/v1/services/', () =>
        HttpResponse.json(
          { name: ['Ya existe un servicio con este nombre.'] },
          { status: 400 },
        ),
      ),
    );
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo servicio' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Corte de cabello');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar servicio' }));

    const dialog = await screen.findByRole('dialog');
    expect(
      await within(dialog).findAllByText('Ya existe un servicio con este nombre.'),
    ).not.toHaveLength(0);
  });

  test('edita un servicio existente', async () => {
    let services = [corte];
    let body: unknown;
    server.use(
      listHandler(() => services),
      http.patch('http://api.test/api/v1/services/service-1/', async ({ request }) => {
        body = await request.json();
        const updated = { ...corte, active: false };
        services = [updated];
        return HttpResponse.json(updated);
      }),
    );
    renderPage();

    const row = await screen.findByRole('row', { name: /Corte de cabello/ });
    await userEvent.click(within(row).getByRole('button', { name: 'Editar' }));
    expect(screen.getByLabelText('Nombre')).toHaveValue('Corte de cabello');
    await userEvent.click(screen.getByRole('checkbox', { name: 'Servicio activo' }));
    await userEvent.click(screen.getByRole('button', { name: 'Guardar servicio' }));

    await waitFor(() => expect(body).toMatchObject({ name: 'Corte de cabello', active: false }));
    expect(await screen.findByText('Inactivo')).toBeInTheDocument();
  });
});
