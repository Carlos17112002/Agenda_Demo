import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test, vi } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { ScheduleSection } from './ScheduleSection';

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

const hours = {
  id: 'hours-1',
  worker: 'worker-1',
  branch: 'branch-1',
  weekday: 0,
  start_time: '09:00:00',
  end_time: '13:00:00',
};

const pause = {
  ...hours,
  id: 'break-1',
  start_time: '11:00:00',
  end_time: '11:30:00',
  label: 'Almuerzo',
};

function renderSection() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <ScheduleSection workerId="worker-1" onWorkerChange={vi.fn()} />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function baseHandlers() {
  return [
    http.get('http://api.test/api/v1/workers/', () =>
      HttpResponse.json({ count: 1, next: null, previous: null, results: [worker] }),
    ),
    http.get('http://api.test/api/v1/working-hours/', () =>
      HttpResponse.json({ count: 1, next: null, previous: null, results: [hours] }),
    ),
    http.get('http://api.test/api/v1/breaks/', () =>
      HttpResponse.json({ count: 1, next: null, previous: null, results: [pause] }),
    ),
  ];
}

describe('ScheduleSection', () => {
  test('muestra turnos y pausas agrupados por sucursal', async () => {
    server.use(...baseHandlers());
    renderSection();

    expect(await screen.findByText('Providencia')).toBeInTheDocument();
    expect(await screen.findByText('Lunes · 09:00 – 13:00')).toBeInTheDocument();
    expect(screen.getByText('Lunes · 11:00 – 11:30')).toBeInTheDocument();
    expect(screen.getByText('Almuerzo')).toBeInTheDocument();
  });

  test('crea un turno para el trabajador', async () => {
    let body: unknown;
    server.use(
      ...baseHandlers(),
      http.post('http://api.test/api/v1/working-hours/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...hours, id: 'hours-2', weekday: 1 }, { status: 201 });
      }),
    );
    renderSection();

    await userEvent.click(await screen.findByRole('button', { name: 'Agregar horario' }));
    await userEvent.selectOptions(screen.getByLabelText('Día'), '1');
    await userEvent.clear(screen.getByLabelText('Inicio'));
    await userEvent.type(screen.getByLabelText('Inicio'), '10:00');
    await userEvent.clear(screen.getByLabelText('Término'));
    await userEvent.type(screen.getByLabelText('Término'), '18:00');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar horario' }));

    await waitFor(() =>
      expect(body).toEqual({
        worker: 'worker-1',
        branch: 'branch-1',
        weekday: 1,
        start_time: '10:00',
        end_time: '18:00',
      }),
    );
  });

  test('rechaza un término anterior al inicio', async () => {
    let posted = false;
    server.use(
      ...baseHandlers(),
      http.post('http://api.test/api/v1/working-hours/', () => {
        posted = true;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    renderSection();

    await userEvent.click(await screen.findByRole('button', { name: 'Agregar horario' }));
    await userEvent.clear(screen.getByLabelText('Término'));
    await userEvent.type(screen.getByLabelText('Término'), '08:00');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar horario' }));

    expect(
      await screen.findByText('La hora de término debe ser posterior al inicio.'),
    ).toBeInTheDocument();
    expect(posted).toBe(false);
  });

  test('elimina un turno tras confirmar', async () => {
    let deleted = '';
    server.use(
      ...baseHandlers(),
      http.delete('http://api.test/api/v1/working-hours/hours-1/', () => {
        deleted = 'hours-1';
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderSection();

    await userEvent.click(
      await screen.findByRole('button', { name: 'Eliminar Lunes 09:00' }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar' }));

    await waitFor(() => expect(deleted).toBe('hours-1'));
  });
});
