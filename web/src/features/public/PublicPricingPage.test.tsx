import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, test } from 'vitest';

import { server } from '../../test/server';
import { PublicPricingPage } from './PublicPricingPage';

const planFixture = {
  id: 'plan-1', code: 'basico', name: 'Básico', description: 'Agenda y clientes.',
  price: '19990.00', currency: 'CLP', billing_period: 'monthly', trial_days: 14,
  is_default: true,
  features: [{ code: 'sales', enabled: true, limit_value: null }],
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PublicPricingPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PublicPricingPage', () => {
  test('lista los planes públicos y abre el formulario de contratación', async () => {
    server.use(
      http.get('http://api.test/api/v1/plans/', () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [planFixture] }),
      ),
    );
    renderPage();

    expect(await screen.findByText('Básico')).toBeInTheDocument();
    expect(screen.getByText('CLP 19.990')).toBeInTheDocument();
    expect(screen.getByText('Ventas')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Contratar' }));
    expect(await screen.findByLabelText('Nombre de la empresa')).toBeInTheDocument();
    expect(screen.getByLabelText('Correo')).toBeInTheDocument();
  });

  test('tras registrar muestra el estado de revisión del correo', async () => {
    server.use(
      http.get('http://api.test/api/v1/plans/', () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [planFixture] }),
      ),
      http.post('http://api.test/api/v1/auth/register-company/', () =>
        HttpResponse.json({
          company_id: 'c-1', company_name: 'Barbería', email: 'dueno@example.com',
          detail: 'Revisa tu correo para activar tu cuenta.',
        }, { status: 201 }),
      ),
    );
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Contratar' }));
    await userEvent.type(screen.getByLabelText('Nombre de la empresa'), 'Barbería');
    await userEvent.type(screen.getByLabelText('Correo'), 'dueno@example.com');
    await userEvent.type(screen.getByLabelText('Contraseña'), 'Clave-Segura-2026!');
    await userEvent.click(screen.getByRole('button', { name: 'Crear cuenta' }));

    expect(await screen.findByText(/Revisa tu correo/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reenviar enlace' })).toBeInTheDocument();
  });
});
