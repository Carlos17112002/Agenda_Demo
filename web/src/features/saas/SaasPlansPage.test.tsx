import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import type { SaasPlan } from '../../api/types';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { SaasPlansPage } from './SaasPlansPage';

const planFixture: SaasPlan = {
  id: 'plan-1',
  code: 'basico',
  name: 'Básico',
  description: 'Agenda y clientes.',
  price: '19990.00',
  currency: 'CLP',
  billing_period: 'monthly',
  trial_days: 14,
  active: true,
  is_default: true,
  sort_order: 0,
  features: [
    { code: 'sales', enabled: true, limit_value: null },
    { code: 'branches', enabled: true, limit_value: 5 },
  ],
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={makeAuthValue({ status: 'saasAdmin', isSaasAdmin: true })}>
        <SaasPlansPage />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
  return queryClient;
}

function useListHandler(plans: SaasPlan[]) {
  server.use(
    http.get('http://api.test/api/v1/saas/plans/', () =>
      HttpResponse.json({ count: plans.length, next: null, previous: null, results: plans }),
    ),
  );
}

describe('SaasPlansPage', () => {
  test('lista los planes con precio, prueba y estado', async () => {
    useListHandler([planFixture]);
    renderPage();

    expect(await screen.findByText('Básico')).toBeInTheDocument();
    expect(screen.getByText('basico')).toBeInTheDocument();
    expect(screen.getByText('CLP 19.990')).toBeInTheDocument();
    expect(screen.getByText('14 días')).toBeInTheDocument();
    expect(screen.getByText('Predeterminado')).toBeInTheDocument();
    expect(screen.getByText('Activo')).toBeInTheDocument();
    expect(screen.getByText(/Sucursales: 5/)).toBeInTheDocument();
  });

  test('muestra un estado vacío cuando no hay planes', async () => {
    useListHandler([]);
    renderPage();

    expect(await screen.findByText('Todavía no hay planes.')).toBeInTheDocument();
  });

  test('crea un plan con funcionalidades y límites', async () => {
    useListHandler([]);
    let body: unknown = null;
    server.use(
      http.post('http://api.test/api/v1/saas/plans/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...planFixture, id: 'plan-2', code: 'pro' }, { status: 201 });
      }),
    );
    renderPage();

    await screen.findByText('Todavía no hay planes.');
    await userEvent.click(screen.getByRole('button', { name: 'Nuevo plan' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Plan Pro');
    await userEvent.type(screen.getByLabelText('Código'), 'pro');
    await userEvent.type(screen.getByLabelText('Precio'), '29990');
    await userEvent.click(screen.getByRole('checkbox', { name: 'Ventas, caja y gastos' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Límite de sucursales' }));
    await userEvent.type(screen.getByLabelText('Máximo de sucursales'), '5');
    await userEvent.click(screen.getByRole('button', { name: 'Crear plan' }));

    await waitFor(() =>
      expect(body).toMatchObject({
        code: 'pro',
        name: 'Plan Pro',
        price: '29990',
        billing_period: 'monthly',
        trial_days: 0,
        features: [
          { code: 'sales', enabled: true },
          { code: 'branches', enabled: true, limit_value: 5 },
        ],
      }),
    );
  });

  test('edita un plan existente', async () => {
    useListHandler([planFixture]);
    let body: unknown = null;
    server.use(
      http.patch('http://api.test/api/v1/saas/plans/plan-1/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...planFixture, name: 'Básico Plus' });
      }),
    );
    renderPage();

    await screen.findByText('Básico');
    await userEvent.click(screen.getByRole('button', { name: 'Editar' }));
    const nameInput = screen.getByLabelText('Nombre');
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, 'Básico Plus');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() => expect(body).toMatchObject({ name: 'Básico Plus' }));
  });

  test('muestra el error del servidor al crear un plan', async () => {
    useListHandler([]);
    server.use(
      http.post('http://api.test/api/v1/saas/plans/', () =>
        HttpResponse.json({ code: ['Ya existe un plan con este código.'] }, { status: 400 }),
      ),
    );
    renderPage();

    await screen.findByText('Todavía no hay planes.');
    await userEvent.click(screen.getByRole('button', { name: 'Nuevo plan' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Plan Pro');
    await userEvent.type(screen.getByLabelText('Código'), 'basico');
    await userEvent.click(screen.getByRole('button', { name: 'Crear plan' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Ya existe un plan con este código.',
    );
  });
});
