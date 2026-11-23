import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, test, vi } from 'vitest';

import { ApiError } from '../../api/client';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { LoginPage } from './LoginPage';

function renderLogin(auth = makeAuthValue({ status: 'anonymous' })) {
  render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/agenda" element={<p>Agenda cargada</p>} />
          <Route path="/saas" element={<p>Panel SaaS cargado</p>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
  return auth;
}

describe('LoginPage', () => {
  test('valida correo y contraseña antes de enviar', async () => {
    const auth = renderLogin();
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(screen.getByText('Ingresa tu correo.')).toBeInTheDocument();
    expect(screen.getByText('Ingresa tu contraseña.')).toBeInTheDocument();
    expect(auth.login).not.toHaveBeenCalled();
  });

  test('envía las credenciales y muestra el error del servidor', async () => {
    const login = vi.fn().mockRejectedValue(new ApiError(401, 'Credenciales inválidas.'));
    renderLogin(makeAuthValue({ status: 'anonymous', login }));

    await userEvent.type(screen.getByLabelText('Correo'), 'owner@agenda.app');
    await userEvent.type(screen.getByLabelText('Contraseña'), 'Secreta2026!');
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(login).toHaveBeenCalledWith('owner@agenda.app', 'Secreta2026!');
    expect(await screen.findByRole('alert')).toHaveTextContent('Credenciales inválidas.');
  });

  test('muestra el aviso de empresa suspendida', async () => {
    renderLogin(
      makeAuthValue({
        status: 'anonymous',
        error: 'Tu empresa está suspendida. Contacta al administrador.',
      }),
    );

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Tu empresa está suspendida. Contacta al administrador.',
    );
  });

  test('con sesión lista redirige a la primera sección permitida', async () => {
    const auth = makeAuthValue({ status: 'ready' });
    renderLogin(auth);
    expect(await screen.findByText('Agenda cargada')).toBeInTheDocument();
  });

  test('un superadmin siempre entra al panel SaaS', async () => {
    renderLogin(makeAuthValue({ status: 'saasAdmin', isSaasAdmin: true }));
    expect(await screen.findByText('Panel SaaS cargado')).toBeInTheDocument();
  });
});
