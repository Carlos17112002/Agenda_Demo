import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { CompanySummary } from '../../api/types';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { ErrorBanner } from '../../components/ui/ErrorBanner';

export function CompanyChooserPage() {
  const { companies, selectCompany, logout, error } = useAuth();
  const navigate = useNavigate();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  async function choose(company: CompanySummary) {
    setPendingId(company.id);
    setLocalError(null);
    try {
      await selectCompany(company);
      navigate('/agenda', { replace: true });
    } catch {
      setLocalError('No se pudo activar la empresa. Intenta nuevamente.');
    } finally {
      setPendingId(null);
    }
  }

  return (
    <main className="min-h-screen bg-surface p-6">
      <div className="mx-auto max-w-3xl">
        <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-brand">AGENDA</p>
            <h1 className="text-2xl font-semibold text-ink">Elige una empresa</h1>
            <p className="mt-1 text-sm text-muted">Solo verás los datos de la empresa activa.</p>
          </div>
          <Button variant="ghost" onClick={() => void logout()}>
            Cerrar sesión
          </Button>
        </header>

        {error || localError ? <ErrorBanner message={localError ?? error ?? ''} /> : null}

        <ul className="mt-6 grid gap-3 sm:grid-cols-2">
          {companies.map((company) => (
            <li key={company.id}>
              <button
                type="button"
                onClick={() => void choose(company)}
                disabled={pendingId !== null}
                className="flex w-full items-center gap-4 rounded-lg border border-line bg-panel p-4 text-left transition hover:border-brand focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-60"
              >
                {company.logo_url ? (
                  <img src={company.logo_url} alt="" className="h-12 w-12 rounded-md object-contain" />
                ) : (
                  <span
                    aria-hidden="true"
                    className="flex h-12 w-12 items-center justify-center rounded-md bg-brand-soft text-lg font-semibold text-brand"
                  >
                    {(company.display_name || company.name).slice(0, 1)}
                  </span>
                )}
                <span>
                  <span className="block font-medium text-ink">{company.display_name || company.name}</span>
                  <span className="block text-sm text-muted">{company.slug}</span>
                </span>
                <span className="ml-auto text-sm text-brand">
                  {pendingId === company.id ? 'Activando…' : 'Entrar'}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
