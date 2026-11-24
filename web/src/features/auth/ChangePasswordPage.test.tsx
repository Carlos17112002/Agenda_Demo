import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, test, vi } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue, makeBootstrap } from '../../test/factories';
import { ForcePasswordChange } from '../../app/guards';
import { ChangePasswordPage } from './ChangePasswordPage';

describe('cambio de clave forzado', () => {
  test('envía la clave actual y la nueva', async () => {
    const changePassword = vi.fn(async () => {});
    const bootstrap = makeBootstrap({
      user: { ...makeBootstrap().user, must_change_password: true },
    });
    render(
      <MemoryRouter initialEntries={['/cambiar-clave']}>
        <AuthContext.Provider value={makeAuthValue({ changePassword, bootstrap })}>
          <Routes>
            <Route path="/cambiar-clave" element={<ChangePasswordPage />} />
            <Route path="/agenda" element={<div>Agenda lista</div>} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>,
    );

    await userEvent.type(screen.getByLabelText('Contraseña actual'), 'Vieja-Clave-123!');
    await userEvent.type(screen.getByLabelText('Nueva contraseña'), 'Nueva-Clave-456!');
    await userEvent.type(screen.getByLabelText('Repetir contraseña'), 'Nueva-Clave-456!');
    await userEvent.click(screen.getByRole('button', { name: 'Actualizar contraseña' }));

    expect(changePassword).toHaveBeenCalledWith('Vieja-Clave-123!', 'Nueva-Clave-456!');
    expect(await screen.findByText('Agenda lista')).toBeInTheDocument();
  });

  test('en modo voluntario confirma y vuelve al panel', async () => {
    const changePassword = vi.fn(async () => {});
    render(
      <MemoryRouter initialEntries={['/cambiar-clave']}>
        <AuthContext.Provider value={makeAuthValue({ changePassword })}>
          <Routes>
            <Route path="/cambiar-clave" element={<ChangePasswordPage />} />
            <Route path="/agenda" element={<div>Agenda lista</div>} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>,
    );

    expect(screen.getByText('Actualiza tu contraseña de acceso.')).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Contraseña actual'), 'Vieja-Clave-123!');
    await userEvent.type(screen.getByLabelText('Nueva contraseña'), 'Nueva-Clave-456!');
    await userEvent.type(screen.getByLabelText('Repetir contraseña'), 'Nueva-Clave-456!');
    await userEvent.click(screen.getByRole('button', { name: 'Actualizar contraseña' }));

    expect(await screen.findByText('Contraseña actualizada')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Volver al panel' }));
    expect(await screen.findByText('Agenda lista')).toBeInTheDocument();
  });

  test('redirige fuera del panel cuando la clave ya fue cambiada', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthContext.Provider value={makeAuthValue()}>
          <Routes>
            <Route
              path="/"
              element={
                <ForcePasswordChange>
                  <div>Panel</div>
                </ForcePasswordChange>
              }
            />
            <Route path="/cambiar-clave" element={<div>Pantalla de cambio</div>} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>,
    );

    expect(screen.getByText('Panel')).toBeInTheDocument();
  });

  test('fuerza la pantalla cuando el bootstrap marca el cambio', () => {
    const bootstrap = makeBootstrap({
      user: { ...makeBootstrap().user, must_change_password: true },
    });
    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthContext.Provider value={makeAuthValue({ bootstrap })}>
          <Routes>
            <Route
              path="/"
              element={
                <ForcePasswordChange>
                  <div>Panel</div>
                </ForcePasswordChange>
              }
            />
            <Route path="/cambiar-clave" element={<div>Pantalla de cambio</div>} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>,
    );

    expect(screen.getByText('Pantalla de cambio')).toBeInTheDocument();
  });
});
