import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test, vi } from 'vitest';

import type { Worker } from '../../api/team';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { WorkersSection } from './WorkersSection';

const paula: Worker = {
  id: 'worker-1',
  company: 'company-a',
  membership: null,
  first_name: 'Paula',
  last_name: 'Rojas',
  display_name: 'Paula Rojas',
  email: 'paula@example.com',
  phone: '+56922222222',
  job_title: 'Estilista',
  color: '#10B981',
  branches: ['branch-1'],
  active: true,
  created_at: '2026-11-01T12:00:00Z',
  updated_at: '2026-11-01T12:00:00Z',
};

function renderSection() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <WorkersSection onManageSchedule={vi.fn()} />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function listHandler(workers: () => Worker[]) {
  return http.get('http://api.test/api/v1/workers/', () => {
    const results = workers();
    return HttpResponse.json({
      count: results.length,
      next: null,
      previous: null,
      results,
    });
  });
}

describe('WorkersSection', () => {
  test('lista trabajadores con cargo, sucursal y estado', async () => {
    server.use(listHandler(() => [paula]));
    renderSection();

    expect(await screen.findByText('Paula Rojas')).toBeInTheDocument();
    expect(screen.getByText('Estilista')).toBeInTheDocument();
    expect(screen.getByText('Providencia')).toBeInTheDocument();
    expect(screen.getByText('Activo')).toBeInTheDocument();
  });

  test('crea un trabajador con sucursal y color', async () => {
    let workers = [paula];
    let body: unknown;
    server.use(
      listHandler(() => workers),
      http.post('http://api.test/api/v1/workers/', async ({ request }) => {
        body = await request.json();
        const created: Worker = {
          ...paula,
          id: 'worker-2',
          first_name: 'Camila',
          last_name: 'Fuentes',
          display_name: 'Camila Fuentes',
          email: '',
          phone: '',
          job_title: 'Colorista',
        };
        workers = [...workers, created];
        return HttpResponse.json(created, { status: 201 });
      }),
    );
    renderSection();

    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo trabajador' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Camila');
    await userEvent.type(screen.getByLabelText('Apellido'), 'Fuentes');
    await userEvent.type(screen.getByLabelText('Cargo'), 'Colorista');
    await userEvent.click(screen.getByRole('checkbox', { name: 'Providencia' }));
    await userEvent.click(screen.getByRole('button', { name: 'Guardar trabajador' }));

    await waitFor(() =>
      expect(body).toEqual({
        first_name: 'Camila',
        last_name: 'Fuentes',
        email: '',
        phone: '',
        job_title: 'Colorista',
        color: '#10B981',
        branches: ['branch-1'],
        active: true,
        membership: null,
      }),
    );
    expect(await screen.findByText('Camila Fuentes')).toBeInTheDocument();
  });

  test('exige al menos una sucursal antes de enviar', async () => {
    let posted = false;
    server.use(
      listHandler(() => [paula]),
      http.post('http://api.test/api/v1/workers/', () => {
        posted = true;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    renderSection();

    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo trabajador' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Camila');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar trabajador' }));

    expect(await screen.findByText('Selecciona al menos una sucursal.')).toBeInTheDocument();
    expect(posted).toBe(false);
  });

  test('edita el cargo de un trabajador', async () => {
    let workers = [paula];
    let body: unknown;
    server.use(
      listHandler(() => workers),
      http.patch('http://api.test/api/v1/workers/worker-1/', async ({ request }) => {
        body = await request.json();
        const updated = { ...paula, job_title: 'Estilista senior' };
        workers = [updated];
        return HttpResponse.json(updated);
      }),
    );
    renderSection();

    const row = await screen.findByRole('row', { name: /Paula Rojas/ });
    await userEvent.click(within(row).getByRole('button', { name: 'Editar' }));
    await userEvent.clear(screen.getByLabelText('Cargo'));
    await userEvent.type(screen.getByLabelText('Cargo'), 'Estilista senior');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar trabajador' }));

    await waitFor(() => expect(body).toMatchObject({ job_title: 'Estilista senior' }));
    expect(await screen.findByText('Estilista senior')).toBeInTheDocument();
  });
});
