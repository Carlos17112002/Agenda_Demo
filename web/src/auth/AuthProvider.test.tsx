import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { describe, expect, test, vi } from 'vitest';

import { ApiError } from '../api/client';
import type { CompanySummary } from '../api/types';
import { createMemorySessionStore, makeBootstrap, makeCompany, makeGateway } from '../test/factories';
import { AuthProvider, useAuth } from './AuthProvider';
import type { SessionStore } from './sessionStore';

function Probe() {
  const auth = useAuth();
  const demo: CompanySummary = makeCompany({ id: 'company-b', name: 'Marca Demo Visual' });
  return (
    <div>
      <span data-testid="status">{auth.status}</span>
      <span data-testid="company">{auth.company?.name ?? ''}</span>
      <span data-testid="companies">
        {auth.companies.map((item) => item.display_name || item.name).join(',')}
      </span>
      <span data-testid="can-write">{auth.can('bookings.write') ? 'si' : 'no'}</span>
      <button onClick={() => auth.selectCompany(demo)}>cambiar</button>
      <button onClick={() => void auth.refreshBootstrap()}>refrescar</button>
      <button onClick={() => auth.logout()}>salir</button>
      <button onClick={() => auth.login('owner@agenda.app', 'Secreta2026!')}>entrar</button>
    </div>
  );
}

function renderAuth(
  store: SessionStore,
  gateway = makeGateway(),
  runtime = { accessToken: null as string | null, tenantContextId: null as string | null },
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const ui: ReactNode = (
    <QueryClientProvider client={queryClient}>
      <AuthProvider gateway={gateway} store={store} runtime={runtime}>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>
  );
  return { queryClient, runtime, ...render(ui) };
}

describe('AuthProvider', () => {
  test('restaura la sesión reutilizando el contexto guardado', async () => {
    const store = createMemorySessionStore({
      refresh: 'refresh-old',
      session: { companyId: 'company-a', contextId: 'ctx-old', companyName: 'Estudio Aurora' },
    });
    const gateway = makeGateway();
    renderAuth(store, gateway);

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'));

    expect(gateway.refresh).toHaveBeenCalledWith('refresh-old');
    expect(gateway.createContext).not.toHaveBeenCalled();
    expect(screen.getByTestId('company')).toHaveTextContent('Estudio Aurora');
    expect(store.state.session?.contextId).toBe('ctx-old');
  });

  test('si el contexto guardado no es válido selecciona la única empresa accesible', async () => {
    const store = createMemorySessionStore({
      refresh: 'refresh-old',
      session: { companyId: 'company-a', contextId: 'ctx-caducado', companyName: 'Estudio Aurora' },
    });
    const bootstrap = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(403, 'Contexto inválido.'))
      .mockResolvedValueOnce(makeBootstrap());
    const gateway = makeGateway({ bootstrap, companies: async () => [makeCompany()] });
    renderAuth(store, gateway);

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'));

    expect(gateway.createContext).toHaveBeenCalledWith('company-a');
    expect(store.state.session?.contextId).toBe('ctx-company-a');
  });

  test('cambiar de empresa crea un contexto nuevo y limpia la caché de consultas', async () => {
    const store = createMemorySessionStore({ refresh: 'refresh-1' });
    const bootstrap = makeBootstrap();
    const gateway = makeGateway({
      bootstrap: async (): Promise<ReturnType<typeof makeBootstrap>> => bootstrap,
      createContext: async (companyId) => ({
        id: `ctx-${companyId}`,
        company: companyId,
        company_name: 'Demo',
        expires_at: '2026-11-11T20:00:00Z',
      }),
    });
    const { queryClient } = renderAuth(store, gateway);
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'));

    queryClient.setQueryData(['bookings', 'company-a', {}], [{ id: 'booking-1' }]);
    await userEvent.click(screen.getByRole('button', { name: 'cambiar' }));

    await waitFor(() => expect(gateway.createContext).toHaveBeenCalledWith('company-b'));
    expect(queryClient.getQueryData(['bookings', 'company-a', {}])).toBeUndefined();
    expect(store.state.session?.companyId).toBe('company-b');
  });

  test('logout limpia tokens, sesión y caché', async () => {
    const store = createMemorySessionStore({ refresh: 'refresh-1' });
    const gateway = makeGateway();
    const { queryClient } = renderAuth(store, gateway);
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'));
    queryClient.setQueryData(['customers', 'company-a', {}], [{ id: 'customer-1' }]);

    await userEvent.click(screen.getByRole('button', { name: 'salir' }));

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'));
    expect(store.state.refresh).toBeNull();
    expect(store.state.session).toBeNull();
    expect(queryClient.getQueryData(['customers', 'company-a', {}])).toBeUndefined();
  });

  test('si el refresh falla al iniciar, deja la sesión anónima', async () => {
    const store = createMemorySessionStore({ refresh: 'refresh-roto' });
    const gateway = makeGateway({
      refresh: async () => {
        throw new ApiError(401, 'Token inválido.');
      },
    });
    renderAuth(store, gateway);

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'));
    expect(store.state.refresh).toBeNull();
  });

  test('el login con una sola empresa selecciona la empresa automáticamente', async () => {
    const store = createMemorySessionStore();
    const gateway = makeGateway({ companies: async () => [makeCompany()] });
    renderAuth(store, gateway);
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'));

    await userEvent.click(screen.getByRole('button', { name: 'entrar' }));

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'));
    expect(gateway.createContext).toHaveBeenCalledWith('company-a');
    expect(store.state.refresh).toBe('refresh-a');
  });

  test('refrescar el bootstrap actualiza también la lista de empresas', async () => {
    const store = createMemorySessionStore({ refresh: 'refresh-1' });
    let list = [makeCompany()];
    const gateway = makeGateway({ companies: async () => list });
    renderAuth(store, gateway);
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'));
    expect(screen.getByTestId('companies')).toHaveTextContent('Estudio Aurora');

    list = [makeCompany({ display_name: 'Aurora Studio' })];
    await userEvent.click(screen.getByRole('button', { name: 'refrescar' }));

    await waitFor(() =>
      expect(screen.getByTestId('companies')).toHaveTextContent('Aurora Studio'),
    );
  });

  test('un evento de sesión expirada limpia el estado', async () => {
    const store = createMemorySessionStore({ refresh: 'refresh-1' });
    renderAuth(store, makeGateway());
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'));

    act(() => {
      window.dispatchEvent(new Event('agenda:session-expired'));
    });

    expect(screen.getByTestId('status')).toHaveTextContent('anonymous');
    expect(store.state.refresh).toBeNull();
  });
});
