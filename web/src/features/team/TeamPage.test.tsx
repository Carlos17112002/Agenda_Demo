import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { TeamPage } from './TeamPage';

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

describe('TeamPage', () => {
  test('abre el horario del trabajador desde la tabla', async () => {
    server.use(
      http.get('http://api.test/api/v1/workers/', () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [worker] }),
      ),
      http.get('http://api.test/api/v1/working-hours/', () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      http.get('http://api.test/api/v1/breaks/', () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <AuthContext.Provider value={makeAuthValue()}>
        <QueryClientProvider client={queryClient}>
          <TeamPage />
        </QueryClientProvider>
      </AuthContext.Provider>,
    );

    const row = await screen.findByRole('row', { name: /Paula Rojas/ });
    await userEvent.click(screen.getByRole('button', { name: 'Horario' }));
    expect(row).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Horario' })).toHaveAttribute('aria-selected', 'true');
    expect(await screen.findByText('Sin turnos.')).toBeInTheDocument();
  });
});
