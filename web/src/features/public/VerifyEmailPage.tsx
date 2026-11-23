import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { ApiError } from '../../api/client';
import { publicAccountsApi, sessionRuntime } from '../../api/runtime';
import { localSessionStore } from '../../auth/sessionStore';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { hardNavigate } from '../../lib/hardNavigate';

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') ?? '';
  const started = useRef(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // StrictMode repite el efecto y el token es de un solo uso.
    if (started.current) return;
    started.current = true;
    if (!token) {
      setError('Falta el enlace de verificación.');
      return;
    }
    publicAccountsApi.verifyEmail(token).then((data) => {
      localSessionStore.writeRefresh(data.refresh);
      sessionRuntime.accessToken = data.access;
      hardNavigate('/');
    }).catch((cause) => {
      setError(cause instanceof ApiError ? cause.message : 'No se pudo verificar la cuenta.');
    });
  }, [token]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface p-6">
      <section className="w-full max-w-sm rounded-xl border border-line bg-panel p-8 text-center shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-wide text-brand">AGENDA</p>
        <h1 className="mt-1 text-2xl font-semibold text-ink">
          {error ? 'No pudimos activar tu cuenta' : 'Activando tu cuenta…'}
        </h1>
        {error ? (
          <div className="mt-4 space-y-4">
            <ErrorBanner message={error} />
            <Link to="/precios" className="text-sm font-medium text-brand hover:underline">
              Volver a los planes
            </Link>
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted">Esto toma solo un momento.</p>
        )}
      </section>
    </main>
  );
}
