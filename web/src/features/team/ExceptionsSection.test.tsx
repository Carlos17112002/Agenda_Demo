import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test, vi } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { ExceptionsSection } from './ExceptionsSection';

const worker = {
  id: 'worker-1',
  company: 'company-a',
  membership: null,
  first_name: 'Paula',
  last_name: 'Rojas',
  display_name: 'Paula Rojas',
  email: '',
  phone: '',
  job_title: 'Estilista',
  color: '#10B981',
  branches: ['branch-1'],
  active: true,
  created_at: '2026-11-01T12:00:00Z',
  updated_at: '2026-11-01T12:00:00Z',
};

const vacation = {
  id: 'timeoff-1',
  worker: 'worker-1',
  branch: 'branch-1',
  starts_at: '2026-11-20T13:00:00Z',
  ends_at: '2026-11-20T15:00:00Z',
  reason: 'Vacaciones',
};

const errand = {
  id: 'blocked-1',
  worker: 'worker-1',
  branch: null,
  starts_at: '2026-11-21T13:00:00Z',
  ends_at: '2026-11-21T14:00:00Z',
  reason: 'Trámite',
};

function renderSection(kind: 'timeOff' | 'blocked') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <ExceptionsSection kind={kind} workerId="worker-1" onWorkerChange={vi.fn()} />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function workersHandler() {
  return http.get('http://api.test/api/v1/workers/', () =>
    HttpResponse.json({ count: 1, next: null, previous: null, results: [worker] }),
  );
}

describe('ExceptionsSection', () => {
  test('lista ausencias con motivo y sucursal', async () => {
    server.use(
      workersHandler(),
      http.get('http://api.test/api/v1/time-off/', () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [vacation] }),
      ),
    );
    renderSection('timeOff');

    expect(await screen.findByText('Providencia · Vacaciones')).toBeInTheDocument();
    expect(screen.getByText(/10:00/)).toBeInTheDocument();
  });

  test('crea una ausencia y convierte la hora local a UTC', async () => {
    let body: unknown;
    server.use(
      workersHandler(),
      http.get('http://api.test/api/v1/time-off/', () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      http.post('http://api.test/api/v1/time-off/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(vacation, { status: 201 });
      }),
    );
    renderSection('timeOff');

    await userEvent.click(await screen.findByRole('button', { name: 'Nueva ausencia' }));
    fireEvent.change(screen.getByLabelText('Inicio'), {
      target: { value: '2026-11-20T10:00' },
    });
    fireEvent.change(screen.getByLabelText('Término'), {
      target: { value: '2026-11-20T12:00' },
    });
    await userEvent.type(screen.getByLabelText('Motivo'), 'Vacaciones');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar ausencia' }));

    await waitFor(() =>
      expect(body).toEqual({
        worker: 'worker-1',
        branch: 'branch-1',
        starts_at: '2026-11-20T13:00:00.000Z',
        ends_at: '2026-11-20T15:00:00.000Z',
        reason: 'Vacaciones',
      }),
    );
  });

  test('rechaza una ausencia que termina antes de empezar', async () => {
    let posted = false;
    server.use(
      workersHandler(),
      http.get('http://api.test/api/v1/time-off/', () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      http.post('http://api.test/api/v1/time-off/', () => {
        posted = true;
        return HttpResponse.json(vacation, { status: 201 });
      }),
    );
    renderSection('timeOff');

    await userEvent.click(await screen.findByRole('button', { name: 'Nueva ausencia' }));
    fireEvent.change(screen.getByLabelText('Inicio'), {
      target: { value: '2026-11-20T12:00' },
    });
    fireEvent.change(screen.getByLabelText('Término'), {
      target: { value: '2026-11-20T10:00' },
    });
    await userEvent.click(screen.getByRole('button', { name: 'Guardar ausencia' }));

    expect(
      await screen.findByText('El término debe ser posterior al inicio.'),
    ).toBeInTheDocument();
    expect(posted).toBe(false);
  });

  test('lista y crea un bloqueo sin sucursal', async () => {
    let body: unknown;
    server.use(
      workersHandler(),
      http.get('http://api.test/api/v1/blocked-slots/', () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [errand] }),
      ),
      http.post('http://api.test/api/v1/blocked-slots/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(errand, { status: 201 });
      }),
    );
    renderSection('blocked');

    expect(await screen.findByText(/Trámite/)).toBeInTheDocument();
    expect(screen.getByText(/Todas las sucursales/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Nuevo bloqueo' }));
    await userEvent.selectOptions(screen.getByLabelText('Sucursal'), '');
    fireEvent.change(screen.getByLabelText('Inicio'), {
      target: { value: '2026-11-21T10:00' },
    });
    fireEvent.change(screen.getByLabelText('Término'), {
      target: { value: '2026-11-21T11:00' },
    });
    await userEvent.type(screen.getByLabelText('Motivo'), 'Trámite');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar bloqueo' }));

    await waitFor(() =>
      expect(body).toEqual({
        worker: 'worker-1',
        branch: null,
        starts_at: '2026-11-21T13:00:00.000Z',
        ends_at: '2026-11-21T14:00:00.000Z',
        reason: 'Trámite',
      }),
    );
  });

  test('elimina una ausencia tras confirmar', async () => {
    let deleted = '';
    server.use(
      workersHandler(),
      http.get('http://api.test/api/v1/time-off/', () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [vacation] }),
      ),
      http.delete('http://api.test/api/v1/time-off/timeoff-1/', () => {
        deleted = 'timeoff-1';
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderSection('timeOff');

    await userEvent.click(
      await screen.findByRole('button', { name: 'Eliminar ausencia Vacaciones' }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar' }));

    await waitFor(() => expect(deleted).toBe('timeoff-1'));
  });
});
