import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, test } from 'vitest';

import { AuthContext } from '../auth/AuthProvider';
import { makeAuthValue } from '../test/factories';
import {
  RequireAuthenticated,
  RequirePermission,
  RequireReady,
  RequireSaasAdmin,
} from './guards';

function renderGuarded(auth = makeAuthValue(), initial = '/agenda') {
  render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route
            path="/agenda"
            element={
              <RequireAuthenticated>
                <RequireReady>
                  <RequirePermission permission="bookings.read">
                    <p>Contenido privado</p>
                  </RequirePermission>
                </RequireReady>
              </RequireAuthenticated>
            }
          />
          <Route path="/" element={<p>Panel de empresa</p>} />
          <Route path="/login" element={<p>Pantalla de acceso</p>} />
          <Route path="/empresa" element={<p>Selector de empresa</p>} />
          <Route path="/sin-acceso" element={<p>Acceso restringido</p>} />
          <Route path="/saas" element={<p>Panel SaaS</p>} />
          <Route
            path="/saas-protegido"
            element={
              <RequireSaasAdmin>
                <p>Empresas SaaS</p>
              </RequireSaasAdmin>
            }
          />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe('guards', () => {
  test('sin sesión redirige al acceso', () => {
    renderGuarded(makeAuthValue({ status: 'anonymous' }));
    expect(screen.getByText('Pantalla de acceso')).toBeInTheDocument();
  });

  test('una sesión sin empresa redirige al selector', () => {
    renderGuarded(makeAuthValue({ status: 'choosingCompany' }));
    expect(screen.getByText('Selector de empresa')).toBeInTheDocument();
  });

  test('sin permiso muestra acceso restringido', () => {
    renderGuarded(makeAuthValue({ can: () => false }));
    expect(screen.getByText('Acceso restringido')).toBeInTheDocument();
  });

  test('con permiso renderiza el contenido', () => {
    renderGuarded();
    expect(screen.getByText('Contenido privado')).toBeInTheDocument();
  });

  test('un superadmin en el panel de empresa es llevado al panel SaaS', () => {
    renderGuarded(makeAuthValue({ status: 'saasAdmin', isSaasAdmin: true }));
    expect(screen.getByText('Panel SaaS')).toBeInTheDocument();
  });

  test('las rutas SaaS exigen ser superadmin', () => {
    renderGuarded(makeAuthValue(), '/saas-protegido');
    expect(screen.getByText('Panel de empresa')).toBeInTheDocument();
    expect(screen.queryByText('Empresas SaaS')).not.toBeInTheDocument();
  });

  test('un superadmin puede abrir las rutas SaaS', () => {
    renderGuarded(makeAuthValue({ status: 'saasAdmin', isSaasAdmin: true }), '/saas-protegido');
    expect(screen.getByText('Empresas SaaS')).toBeInTheDocument();
  });
});
