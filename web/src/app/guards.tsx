import type { ReactNode } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/AuthProvider';
import { Skeleton } from '../components/ui/Skeleton';
import { firstAllowedPath } from '../lib/permissions';

function FullPageLoading() {
  return (
    <main className="p-8">
      <Skeleton rows={6} />
    </main>
  );
}

export function RequireAuthenticated({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === 'loading') return <FullPageLoading />;
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

export function RequireReady({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  if (status === 'choosingCompany') return <Navigate to="/empresa" replace />;
  if (status !== 'ready') return <FullPageLoading />;
  return <>{children}</>;
}

export function ForcePasswordChange({ children }: { children: ReactNode }) {
  const { status, bootstrap } = useAuth();
  if (status === 'loading') return <FullPageLoading />;
  if (bootstrap?.user.must_change_password) return <Navigate to="/cambiar-clave" replace />;
  return <>{children}</>;
}

export function RequirePermission({
  permission,
  children,
}: {
  permission: string;
  children: ReactNode;
}) {
  const { can } = useAuth();
  if (!can(permission)) return <Navigate to="/sin-acceso" replace />;
  return <>{children}</>;
}

export function AccessDeniedPage() {
  const { can, hasFeature } = useAuth();
  const target = firstAllowedPath(can, hasFeature);
  return (
    <section className="mx-auto max-w-lg rounded-lg border border-line bg-panel p-8 text-center">
      <h1 className="text-xl font-semibold text-ink">Acceso restringido</h1>
      <p className="mt-2 text-sm text-muted">
        No tienes permiso para esta sección con tu rol actual.
      </p>
      {target !== '/sin-acceso' ? (
        <Link className="mt-4 inline-block text-sm font-medium text-brand underline" to={target}>
          Ir a una sección disponible
        </Link>
      ) : null}
    </section>
  );
}

export function NotFoundPage() {
  return (
    <section className="mx-auto max-w-lg rounded-lg border border-line bg-panel p-8 text-center">
      <h1 className="text-xl font-semibold text-ink">Página no encontrada</h1>
      <p className="mt-2 text-sm text-muted">La ruta solicitada no existe en el panel.</p>
    </section>
  );
}
