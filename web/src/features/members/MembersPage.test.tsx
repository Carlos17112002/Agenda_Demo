import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, test } from 'vitest';

import type { Member } from '../../api/members';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { MembersPage } from './MembersPage';

const memberFixture: Member = {
  id: 'membership-2',
  user_id: 'user-2',
  email: 'nueva@example.com',
  first_name: 'Nueva',
  last_name: 'Persona',
  role: 'reception',
  role_display: 'Recepción',
  default_branch: { id: 'branch-1', name: 'Providencia' },
  active: true,
  created_at: '2026-11-19T12:00:00Z',
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <MemoryRouter>
      <AuthContext.Provider value={makeAuthValue()}>
        <QueryClientProvider client={queryClient}>
          <MembersPage />
        </QueryClientProvider>
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

describe('MembersPage', () => {
  test('lista usuarios y muestra el local asignado', async () => {
    server.use(
      http.get('http://api.test/api/v1/members/', () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [memberFixture] }),
      ),
    );
    renderPage();

    expect(await screen.findByText('nueva@example.com')).toBeInTheDocument();
    expect(screen.getByText('Providencia')).toBeInTheDocument();
    expect(screen.getByText('Recepción')).toBeInTheDocument();
  });

  test('crea un usuario y muestra la clave temporal una sola vez', async () => {
    let body: unknown = null;
    server.use(
      http.get('http://api.test/api/v1/members/', () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      http.post('http://api.test/api/v1/members/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          { member: memberFixture, temporary_password: 'Temp-Phrase-123!', worker_profile: null },
          { status: 201 },
        );
      }),
    );
    renderPage();

    await screen.findByText('Todavía no hay usuarios.');
    await userEvent.click(screen.getByRole('button', { name: 'Nuevo usuario' }));
    await userEvent.type(screen.getByLabelText('Correo'), 'nueva@example.com');
    await userEvent.type(screen.getByLabelText('Nombre'), 'Nueva');
    await userEvent.selectOptions(screen.getByLabelText('Rol'), 'reception');
    await userEvent.selectOptions(screen.getByLabelText('Local predeterminado'), 'branch-1');
    await userEvent.click(screen.getByRole('button', { name: 'Crear usuario' }));

    await waitFor(() =>
      expect(body).toMatchObject({
        email: 'nueva@example.com',
        role: 'reception',
        default_branch: 'branch-1',
      }),
    );
    expect(await screen.findByText('Temp-Phrase-123!')).toBeInTheDocument();
    expect(screen.getByText('Credenciales de acceso')).toBeInTheDocument();
  });
});
