import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, test, vi } from 'vitest';

import { REFRESH_KEY } from '../../auth/sessionStore';
import { server } from '../../test/server';
import { VerifyEmailPage } from './VerifyEmailPage';

vi.mock('../../lib/hardNavigate', () => ({ hardNavigate: vi.fn() }));

function renderPage(token: string) {
  render(
    <MemoryRouter initialEntries={[`/verificar?token=${token}`]}>
      <Routes>
        <Route path="/verificar" element={<VerifyEmailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('VerifyEmailPage', () => {
  test('guarda la sesión y entra al panel cuando el token es válido', async () => {
    server.use(
      http.post('http://api.test/api/v1/auth/verify-email/', () =>
        HttpResponse.json({
          access: 'access-1', refresh: 'refresh-1',
          user: {
            id: 'u-1', email: 'dueno@example.com', first_name: 'Dueña', last_name: '',
            is_saas_admin: false, is_superuser: false, must_change_password: false,
          },
        }),
      ),
    );
    const { hardNavigate } = await import('../../lib/hardNavigate');
    renderPage('token-valido');

    expect(await screen.findByText(/Activando tu cuenta/i)).toBeInTheDocument();
    await vi.waitFor(() => expect(hardNavigate).toHaveBeenCalledWith('/'));
    expect(localStorage.getItem(REFRESH_KEY)).toBe('refresh-1');
  });

  test('muestra el error cuando el token venció', async () => {
    server.use(
      http.post('http://api.test/api/v1/auth/verify-email/', () =>
        HttpResponse.json({ token: ['El enlace no es válido o venció.'] }, { status: 400 }),
      ),
    );
    renderPage('token-vencido');
    expect(await screen.findByText('El enlace no es válido o venció.')).toBeInTheDocument();
  });
});
