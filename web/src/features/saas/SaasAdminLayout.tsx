import { Outlet, useNavigate } from 'react-router-dom';

import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { useTheme } from '../../theme/ThemeProvider';

export function SaasAdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { mode, toggleMode } = useTheme();

  async function signOut() {
    await logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b border-line bg-panel px-4 py-3">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-brand">AGENDA</p>
            <p className="text-base font-semibold text-ink">Consola de superadmin</p>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <span className="truncate text-xs text-muted" title={user?.email}>
              {user?.email}
            </span>
            <Button variant="ghost" onClick={toggleMode}>
              {mode === 'dark' ? 'Tema claro' : 'Tema oscuro'}
            </Button>
            <Button variant="ghost" onClick={() => void signOut()}>
              Salir
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl p-4 lg:p-6">
        <Outlet />
      </main>
    </div>
  );
}
