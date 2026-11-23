import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test, vi } from 'vitest';

import type { Member } from '../../api/members';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { PermissionsDialog } from './PermissionsDialog';

const member: Member = {
  id: 'membership-2',
  user_id: 'user-2',
  email: 'reception@example.com',
  first_name: 'Rita',
  last_name: 'Recepción',
  role: 'reception',
  role_display: 'Recepción',
  default_branch: { id: 'branch-1', name: 'Providencia' },
  active: true,
  created_at: '2026-11-19T12:00:00Z',
};

describe('PermissionsDialog', () => {
  test('crea un permiso denegado en un local', async () => {
    let body: unknown = null;
    server.use(
      http.get('http://api.test/api/v1/permission-grants/', () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      http.post('http://api.test/api/v1/permission-grants/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          {
            id: 'grant-1',
            membership: 'membership-2',
            permission: 'bookings.write',
            effect: 'deny',
            branch: 'branch-1',
            created_at: '2026-11-19T12:00:00Z',
          },
          { status: 201 },
        );
      }),
    );
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <AuthContext.Provider value={makeAuthValue()}>
        <QueryClientProvider client={queryClient}>
          <PermissionsDialog open member={member} onOpenChange={vi.fn()} onSaved={vi.fn()} />
        </QueryClientProvider>
      </AuthContext.Provider>,
    );

    await screen.findByText('Gestionar reservas');
    await userEvent.selectOptions(screen.getByLabelText('Efecto para Gestionar reservas'), 'deny');
    await userEvent.selectOptions(
      screen.getByLabelText('Alcance para Gestionar reservas'),
      'branch-1',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Guardar permisos' }));

    await waitFor(() =>
      expect(body).toEqual({
        membership: 'membership-2',
        permission: 'bookings.write',
        effect: 'deny',
        branch: 'branch-1',
      }),
    );
  });
});
