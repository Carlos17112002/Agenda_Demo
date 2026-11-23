import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, test, vi } from 'vitest';

import { AuthContext } from '../auth/AuthProvider';
import { ThemeProvider } from '../theme/ThemeProvider';
import { makeAuthValue, makeCompany } from '../test/factories';
import { AppLayout } from './AppLayout';

function renderLayout(auth = makeAuthValue()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={auth}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider companyMode="light">
          <MemoryRouter initialEntries={['/agenda']}>
            <Routes>
              <Route element={<AppLayout />}>
                <Route path="/agenda" element={<p>Contenido de agenda</p>} />
              </Route>
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
  return { auth, queryClient };
}

describe('AppLayout', () => {
  test('muestra solo las secciones permitidas y el usuario', () => {
    renderLayout(makeAuthValue({ can: (permission) => permission !== 'reports.read' }));
    expect(screen.getByRole('link', { name: 'Agenda' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Resumen' })).not.toBeInTheDocument();
    expect(screen.getByText('owner@agenda.app')).toBeInTheDocument();
    expect(screen.getByText('Contenido de agenda')).toBeInTheDocument();
  });

  test('permite cambiar de empresa', async () => {
    const selectCompany = vi.fn().mockResolvedValue(undefined);
    const auth = makeAuthValue({
      companies: [
        makeCompany({ id: 'company-a', display_name: 'Estudio Aurora' }),
        makeCompany({ id: 'company-b', display_name: 'Marca Demo Visual' }),
      ],
      selectCompany,
    });
    renderLayout(auth);

    await userEvent.selectOptions(screen.getByLabelText('Empresa'), 'company-b');

    expect(selectCompany).toHaveBeenCalledWith(expect.objectContaining({ id: 'company-b' }));
  });

  test('alterna el tema y cierra la sesión', async () => {
    const logout = vi.fn().mockResolvedValue(undefined);
    renderLayout(makeAuthValue({ logout }));

    await userEvent.click(screen.getByRole('button', { name: 'Tema oscuro' }));
    expect(sessionStorage.getItem('agenda.web.theme')).toBe('dark');

    await userEvent.click(screen.getByRole('button', { name: 'Salir' }));
    expect(logout).toHaveBeenCalledTimes(1);
  });

  test('el botón actualizar recarga bootstrap e invalida consultas', async () => {
    const refreshBootstrap = vi.fn().mockResolvedValue(undefined);
    const { queryClient } = renderLayout(makeAuthValue({ refreshBootstrap }));
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');

    await userEvent.click(screen.getByRole('button', { name: 'Actualizar' }));

    expect(refreshBootstrap).toHaveBeenCalledTimes(1);
    expect(invalidate).toHaveBeenCalled();
  });
});
