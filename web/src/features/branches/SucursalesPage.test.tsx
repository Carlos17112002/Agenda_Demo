import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import type { Branch } from '../../api/types';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { SucursalesPage } from './SucursalesPage';

const branchFixture: Branch = {
  id: 'branch-1',
  company: 'company-a',
  name: 'Providencia',
  code: 'PROV',
  address: 'Av. Providencia 123',
  timezone: 'America/Santiago',
  active: true,
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const auth = makeAuthValue();
  render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={auth}>
        <SucursalesPage />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
  return auth;
}

function useListHandler(branches: Branch[]) {
  server.use(
    http.get('http://api.test/api/v1/branches/', () =>
      HttpResponse.json({
        count: branches.length,
        next: null,
        previous: null,
        results: branches,
      }),
    ),
  );
}

describe('SucursalesPage', () => {
  test('lista las sucursales de la empresa', async () => {
    useListHandler([branchFixture]);
    renderPage();

    expect(await screen.findByText('Providencia')).toBeInTheDocument();
    expect(screen.getByText('PROV')).toBeInTheDocument();
    expect(screen.getByText('Av. Providencia 123')).toBeInTheDocument();
    expect(screen.getByText('Activa')).toBeInTheDocument();
  });

  test('muestra un estado vacío cuando no hay sucursales', async () => {
    useListHandler([]);
    renderPage();

    expect(await screen.findByText('Todavía no hay sucursales.')).toBeInTheDocument();
  });

  test('crea una sucursal y refresca el bootstrap', async () => {
    useListHandler([]);
    let body: unknown = null;
    server.use(
      http.post('http://api.test/api/v1/branches/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          { ...branchFixture, id: 'branch-2', name: 'Nueva Sede' },
          { status: 201 },
        );
      }),
    );
    const auth = renderPage();

    await screen.findByText('Todavía no hay sucursales.');
    await userEvent.click(screen.getByRole('button', { name: 'Nueva sucursal' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Nueva Sede');
    await userEvent.type(screen.getByLabelText('Código'), 'NUEVA');
    await userEvent.type(screen.getByLabelText('Dirección'), 'Los Leones 456');
    await userEvent.click(screen.getByRole('button', { name: 'Crear sucursal' }));

    await waitFor(() =>
      expect(body).toMatchObject({
        name: 'Nueva Sede',
        code: 'NUEVA',
        address: 'Los Leones 456',
        timezone: 'America/Santiago',
      }),
    );
    await waitFor(() => expect(auth.refreshBootstrap).toHaveBeenCalled());
  });

  test('edita una sucursal existente', async () => {
    useListHandler([branchFixture]);
    let body: unknown = null;
    server.use(
      http.patch('http://api.test/api/v1/branches/branch-1/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...branchFixture, name: 'Providencia Centro' });
      }),
    );
    renderPage();

    await screen.findByText('Providencia');
    await userEvent.click(screen.getByRole('button', { name: 'Editar' }));
    const nameInput = screen.getByLabelText('Nombre');
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, 'Providencia Centro');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() => expect(body).toMatchObject({ name: 'Providencia Centro' }));
  });

  test('desactiva una sucursal tras confirmar', async () => {
    let branches = [branchFixture];
    server.use(
      http.get('http://api.test/api/v1/branches/', () =>
        HttpResponse.json({ count: branches.length, next: null, previous: null, results: branches }),
      ),
      http.delete('http://api.test/api/v1/branches/branch-1/', () => {
        branches = [{ ...branchFixture, active: false }];
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderPage();

    await screen.findByText('Providencia');
    await userEvent.click(screen.getByRole('button', { name: 'Desactivar' }));
    await userEvent.click(screen.getByRole('button', { name: 'Sí, desactivar' }));

    expect(await screen.findByText('Inactiva')).toBeInTheDocument();
  });

  test('muestra el error del servidor al crear una sucursal', async () => {
    useListHandler([]);
    server.use(
      http.post('http://api.test/api/v1/branches/', () =>
        HttpResponse.json(
          { code: ['Ya existe una sucursal con ese código en la empresa.'] },
          { status: 400 },
        ),
      ),
    );
    renderPage();

    await screen.findByText('Todavía no hay sucursales.');
    await userEvent.click(screen.getByRole('button', { name: 'Nueva sucursal' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Nueva Sede');
    await userEvent.type(screen.getByLabelText('Código'), 'PROV');
    await userEvent.click(screen.getByRole('button', { name: 'Crear sucursal' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Ya existe una sucursal con ese código en la empresa.',
    );
  });
});
