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
  is_default: false,
  sort_order: 0,
  features: [],
};

const premiumFixture: SaasPlan = {
  ...planFixture,
  id: 'plan-2',
  code: 'premium',
  name: 'Premium',
  is_default: false,
  sort_order: 1,
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

function useListHandlers(
  companies: SaasCompany[],
  onCompaniesRequest?: () => void,
) {
  server.use(
    http.get('http://api.test/api/v1/saas/companies/', () => {
      onCompaniesRequest?.();
      return HttpResponse.json({
        count: companies.length,
        next: null,
        previous: null,
        results: companies,
      });
    }),
    http.get('http://api.test/api/v1/saas/plans/', () =>
      HttpResponse.json({
        count: 2,
        next: null,
        previous: null,
        results: [planFixture, premiumFixture],
      }),
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

  test('muestra el estado real de la empresa', async () => {
    useListHandlers([
      { ...companyFixture, status: 'suspended' },
      {
        ...companyFixture,
        id: 'saas-company-2',
        name: 'Marca en Prueba',
        slug: 'marca-en-prueba',
        status: 'trial',
      },
      {
        ...companyFixture,
        id: 'saas-company-3',
        name: 'Marca Cerrada',
        slug: 'marca-cerrada',
        status: 'closed',
      },
    ]);
    renderPage();

    expect(await screen.findByText('Suspendida')).toBeInTheDocument();
    expect(screen.getByText('Prueba')).toBeInTheDocument();
    expect(screen.getByText('Cerrada')).toBeInTheDocument();
  });

  test('cambia el plan de una empresa sin tocar su estado', async () => {
    let listRequests = 0;
    useListHandlers([companyFixture], () => {
      listRequests += 1;
    });
    let planBody: unknown = null;
    let statusCalled = false;
    server.use(
      http.post(
        'http://api.test/api/v1/saas/subscriptions/subscription-1/change-plan/',
        async ({ request }) => {
          planBody = await request.json();
          return HttpResponse.json({});
        },
      ),
      http.post('http://api.test/api/v1/saas/companies/saas-company-1/change-status/', () => {
        statusCalled = true;
        return HttpResponse.json(companyFixture);
      }),
    );
    renderPage();

    await screen.findByText('Estudio Aurora');
    await userEvent.click(screen.getByRole('button', { name: 'Editar' }));
    await userEvent.selectOptions(await screen.findByLabelText('Plan'), 'plan-2');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() => expect(planBody).toEqual({ plan: 'plan-2' }));
    expect(statusCalled).toBe(false);
    await waitFor(() => expect(listRequests).toBe(2));
  });

  test('suspende una empresa desde el interruptor', async () => {
    useListHandlers([companyFixture]);
    let statusBody: unknown = null;
    server.use(
      http.post(
        'http://api.test/api/v1/saas/companies/saas-company-1/change-status/',
        async ({ request }) => {
          statusBody = await request.json();
          return HttpResponse.json({ ...companyFixture, status: 'suspended' });
        },
      ),
    );
    renderPage();

    await screen.findByText('Estudio Aurora');
    await userEvent.click(screen.getByRole('button', { name: 'Editar' }));
    const toggle = await screen.findByLabelText('Empresa activa');
    expect(toggle).toBeChecked();
    await userEvent.click(toggle);
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() => expect(statusBody).toEqual({ status: 'suspended' }));
  });

  test('reactiva una empresa suspendida', async () => {
    useListHandlers([{ ...companyFixture, status: 'suspended' }]);
    let statusBody: unknown = null;
    server.use(
      http.post(
        'http://api.test/api/v1/saas/companies/saas-company-1/change-status/',
        async ({ request }) => {
          statusBody = await request.json();
          return HttpResponse.json({ ...companyFixture, status: 'active' });
        },
      ),
    );
    renderPage();

    await screen.findByText('Estudio Aurora');
    await userEvent.click(screen.getByRole('button', { name: 'Editar' }));
    const toggle = await screen.findByLabelText('Empresa activa');
    expect(toggle).not.toBeChecked();
    await userEvent.click(toggle);
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() => expect(statusBody).toEqual({ status: 'active' }));
  });

  test('sin suscripción abierta no permite cambiar el plan', async () => {
    useListHandlers([{ ...companyFixture, subscription: null }]);
    renderPage();

    await screen.findByText('Estudio Aurora');
    await userEvent.click(screen.getByRole('button', { name: 'Editar' }));

    expect(await screen.findByLabelText('Plan')).toBeDisabled();
    expect(screen.getByText('La empresa no tiene una suscripción abierta.')).toBeInTheDocument();
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
