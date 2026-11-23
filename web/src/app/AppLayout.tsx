import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthProvider';
import { Button } from '../components/ui/Button';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { NAV_ITEMS, visibleNav } from '../lib/permissions';
import { useOnlineStatus } from '../lib/useOnlineStatus';
import { useTheme } from '../theme/ThemeProvider';

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `block whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition ${
    isActive ? 'bg-brand-soft text-ink' : 'text-ink hover:bg-surface'
  }`;

export function AppLayout() {
  const {
    company,
    companies,
    user,
    can,
    hasFeature,
    bootstrap,
    logout,
    selectCompany,
    refreshBootstrap,
  } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const online = useOnlineStatus();
  const { mode, toggleMode } = useTheme();
  const [refreshing, setRefreshing] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [layoutError, setLayoutError] = useState<string | null>(null);
  const nav = visibleNav(can, hasFeature, NAV_ITEMS, bootstrap?.membership.role === 'owner');

  async function reload() {
    setRefreshing(true);
    setLayoutError(null);
    try {
      await refreshBootstrap();
      await queryClient.invalidateQueries();
    } catch (error) {
      setLayoutError(error instanceof ApiError ? error.message : 'No se pudo actualizar el panel.');
    } finally {
      setRefreshing(false);
    }
  }

  async function switchCompany(companyId: string) {
    const target = companies.find((item) => item.id === companyId);
    if (!target) return;
    setSwitching(true);
    setLayoutError(null);
    try {
      await selectCompany(target);
      navigate('/agenda', { replace: true });
    } catch (error) {
      setLayoutError(
        error instanceof ApiError ? error.message : 'No se pudo cambiar de empresa.',
      );
    } finally {
      setSwitching(false);
    }
  }

  async function signOut() {
    await logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="min-h-screen bg-surface md:flex">
      <aside className="border-b border-line bg-panel md:flex md:w-56 md:shrink-0 md:flex-col md:border-b-0 md:border-r">
        <div className="border-b border-line px-4 py-4 md:py-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">AGENDA</p>
          {company?.logo_url ? (
            <img src={company.logo_url} alt="" className="mt-2 h-8 max-w-[10rem] object-contain" />
          ) : null}
          <p className="mt-1 truncate text-base font-semibold text-ink">
            {company?.display_name || company?.name}
          </p>
        </div>
        <nav aria-label="Secciones" className="flex gap-1 overflow-x-auto p-3 md:flex-1 md:flex-col md:space-y-1">
          {nav.map((item) => (
            <NavLink key={item.path} to={item.path} className={linkClass}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-line px-3 py-2 text-xs text-muted">
          <p className="truncate" title={user?.email}>
            {user?.email}
          </p>
          <p>{bootstrap?.membership.role_display}</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-line bg-panel px-4 py-3">
          <div className="flex flex-wrap items-center gap-3">
            <p className="font-semibold text-ink md:hidden">AGENDA</p>
            {companies.length > 1 ? (
              <label htmlFor="company-switcher" className="flex items-center gap-2 text-sm text-muted">
                Empresa
                <select
                  id="company-switcher"
                  value={company?.id ?? ''}
                  disabled={switching}
                  onChange={(event) => void switchCompany(event.target.value)}
                  className="rounded-md border border-line bg-panel px-2 py-1 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
                >
                  {companies.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.display_name || item.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <div className="ml-auto flex flex-wrap items-center gap-2">
              <Button
                variant="secondary"
                onClick={() => void reload()}
                loading={refreshing}
                loadingLabel="Actualizando…"
              >
                Actualizar
              </Button>
              <Button variant="ghost" onClick={toggleMode}>
                {mode === 'dark' ? 'Tema claro' : 'Tema oscuro'}
              </Button>
              <Button variant="ghost" onClick={() => void signOut()}>
                Salir
              </Button>
            </div>
          </div>

          {!online ? (
            <div className="mt-3">
              <ErrorBanner
                message="Sin conexión con el servidor."
                onRetry={() => void queryClient.refetchQueries({ type: 'active' })}
              />
            </div>
          ) : null}
          {layoutError ? (
            <div className="mt-3">
              <ErrorBanner message={layoutError} />
            </div>
          ) : null}
        </header>

        <main className="min-w-0 flex-1 p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
