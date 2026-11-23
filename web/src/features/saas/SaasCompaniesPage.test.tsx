import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import type { SaasCompany, SaasPlan } from '../../api/types';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { SaasCompaniesPage } from './SaasCompaniesPage';

const companyFixture: SaasCompany = {
  id: 'saas-company-1',
  name: 'Estudio Aurora',
  slug: 'estudio-aurora',
  legal_name: '',
  tax_identifier: '',
  status: 'active',
  created_at: '2026-11-20T12:00:00Z',
  updated_at: '2026-11-20T12:00:00Z',
  subscription: {
    id: 'subscription-1',
    plan: 'basico',
    status: 'active',
    effective_status: 'active',
    usable: true,
    current_period_end: '2026-12-20T12:00:00Z',
    trial_ends_at: null,
  },
};

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
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={makeAuthValue({ status: 'saasAdmin', isSaasAdmin: true })}>
        <SaasCompaniesPage />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
  return queryClient;
}

function useListHandlers(companies: SaasCompany[]) {
  server.use(
    http.get('http://api.test/api/v1/saas/companies/', () =>
      HttpResponse.json({ count: companies.length, next: null, previous: null, results: companies }),
    ),
    http.get('http://api.test/api/v1/saas/plans/', () =>
      HttpResponse.json({ count: 1, next: null, previous: null, results: [planFixture] }),
    ),
  );
}

describe('SaasCompaniesPage', () => {
  test('lista las empresas con su plan y estado', async () => {
    useListHandlers([companyFixture]);
    renderPage();

    expect(await screen.findByText('Estudio Aurora')).toBeInTheDocument();
    expect(await screen.findByText('Básico')).toBeInTheDocument();
    expect(screen.getByText('Activa')).toBeInTheDocument();
    expect(screen.getByText('2026-12-20')).toBeInTheDocument();
  });

  test('muestra un estado vacío cuando no hay empresas', async () => {
    useListHandlers([]);
    renderPage();

    expect(await screen.findByText('Todavía no hay empresas.')).toBeInTheDocument();
  });

  test('crea una empresa y entrega la clave temporal una sola vez', async () => {
    useListHandlers([]);
    let body: unknown = null;
    server.use(
      http.post('http://api.test/api/v1/saas/companies/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          {
            company_id: 'saas-company-2',
            company_name: 'Nueva Marca',
            slug: 'nueva-marca',
            owner_id: 'user-9',
            owner_email: 'duena@nuevamarca.cl',
            owner_name: 'Dueña',
            temporary_password: 'Temp-Marca-2026!',
            booking_url: 'https://agenda.test/b/nueva-marca/',
            subscription: null,
            detail: 'Empresa creada.',
          },
          { status: 201 },
        );
      }),
    );
    renderPage();

    await screen.findByText('Todavía no hay empresas.');
    await userEvent.click(screen.getByRole('button', { name: 'Nueva empresa' }));
    await userEvent.type(screen.getByLabelText('Nombre de la empresa'), 'Nueva Marca');
    await userEvent.type(screen.getByLabelText('Correo del propietario'), 'duena@nuevamarca.cl');
    await screen.findByRole('option', { name: 'Básico' });
    await userEvent.selectOptions(screen.getByLabelText('Plan'), 'basico');
    await userEvent.click(screen.getByRole('button', { name: 'Crear empresa' }));

    await waitFor(() =>
      expect(body).toMatchObject({
        company_name: 'Nueva Marca',
        slug: 'nueva-marca',
        email: 'duena@nuevamarca.cl',
        plan: 'basico',
      }),
    );
    expect(await screen.findByTestId('temporary-password')).toHaveTextContent('Temp-Marca-2026!');
    expect(screen.getByText('duena@nuevamarca.cl')).toBeInTheDocument();
    expect(screen.getByText('https://agenda.test/b/nueva-marca/')).toBeInTheDocument();
  });

  test('muestra el error del servidor al crear una empresa', async () => {
    useListHandlers([]);
    server.use(
      http.post('http://api.test/api/v1/saas/companies/', () =>
        HttpResponse.json({ slug: ['Ya existe una empresa con ese identificador.'] }, { status: 400 }),
      ),
    );
    renderPage();

    await screen.findByText('Todavía no hay empresas.');
    await userEvent.click(screen.getByRole('button', { name: 'Nueva empresa' }));
    await userEvent.type(screen.getByLabelText('Nombre de la empresa'), 'Nueva Marca');
    await userEvent.type(screen.getByLabelText('Correo del propietario'), 'duena@nuevamarca.cl');
    await screen.findByRole('option', { name: 'Básico' });
    await userEvent.selectOptions(screen.getByLabelText('Plan'), 'basico');
    await userEvent.click(screen.getByRole('button', { name: 'Crear empresa' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Ya existe una empresa con ese identificador.',
    );
  });
});
