import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { queryKeys } from '../../api/queryKeys';
import { branchesApi } from '../../api/runtime';
import type { Branch } from '../../api/types';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/Dialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { PageHeader } from '../../components/ui/PageHeader';
import { Skeleton } from '../../components/ui/Skeleton';
import { BranchFormDialog } from './BranchFormDialog';

export function SucursalesPage() {
  const { company, bootstrap, refreshBootstrap } = useAuth();
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Branch | null>(null);
  const [deactivating, setDeactivating] = useState<Branch | null>(null);

  const branchesQuery = useQuery({
    queryKey: queryKeys.branches(company?.id ?? ''),
    queryFn: () => branchesApi.list(),
    enabled: Boolean(company),
  });

  const isOwner = bootstrap?.membership.role === 'owner';

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ['branches'] });
    await refreshBootstrap();
  };

  const deactivate = useMutation({
    mutationFn: (branch: Branch) => branchesApi.remove(branch.id),
    onSuccess: async () => {
      setDeactivating(null);
      await invalidate();
    },
  });

  const activate = useMutation({
    mutationFn: (branch: Branch) => branchesApi.update(branch.id, { active: true }),
    onSuccess: invalidate,
  });

  const rows = branchesQuery.data?.results ?? [];

  return (
    <section>
      <PageHeader
        title="Sucursales"
        description="Los locales de la empresa. Cada sucursal tiene su propia agenda y equipo."
        actions={
          isOwner ? (
            <Button
              onClick={() => {
                setEditing(null);
                setFormOpen(true);
              }}
            >
              Nueva sucursal
            </Button>
          ) : null
        }
      />

      {branchesQuery.error ? (
        <ErrorBanner
          message="No se pudieron cargar las sucursales."
          onRetry={() => void branchesQuery.refetch()}
        />
      ) : null}

      {branchesQuery.isPending ? <Skeleton rows={4} /> : null}

      {!branchesQuery.isPending && rows.length === 0 ? (
        <EmptyState
          title="Todavía no hay sucursales."
          description="Crea la primera sucursal para organizar la agenda de la empresa."
        />
      ) : null}

      {rows.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-line bg-panel">
          <table className="min-w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3">Nombre</th>
                <th className="px-4 py-3">Código</th>
                <th className="px-4 py-3">Dirección</th>
                <th className="px-4 py-3">Zona horaria</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((branch) => (
                <tr key={branch.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-3 font-medium text-ink">{branch.name}</td>
                  <td className="px-4 py-3">{branch.code}</td>
                  <td className="px-4 py-3">{branch.address || '—'}</td>
                  <td className="px-4 py-3">{branch.timezone}</td>
                  <td className="px-4 py-3">
                    <Badge tone={branch.active ? 'active' : 'inactive'}>
                      {branch.active ? 'Activa' : 'Inactiva'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    {isOwner ? (
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="secondary"
                          onClick={() => {
                            setEditing(branch);
                            setFormOpen(true);
                          }}
                        >
                          Editar
                        </Button>
                        {branch.active ? (
                          <Button variant="danger" onClick={() => setDeactivating(branch)}>
                            Desactivar
                          </Button>
                        ) : (
                          <Button variant="secondary" onClick={() => activate.mutate(branch)}>
                            Reactivar
                          </Button>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-muted">Solo el propietario</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <BranchFormDialog
        open={formOpen}
        branch={editing}
        onOpenChange={(next) => {
          setFormOpen(next);
          if (!next) setEditing(null);
        }}
        onSaved={() => void invalidate()}
      />

      <ConfirmDialog
        open={Boolean(deactivating)}
        onOpenChange={(next) => {
          if (!next) setDeactivating(null);
        }}
        title="Desactivar sucursal"
        description="La sucursal dejará de estar disponible en la agenda, pero conservará sus datos."
        confirmLabel="Sí, desactivar"
        loading={deactivate.isPending}
        onConfirm={() => {
          if (deactivating) deactivate.mutate(deactivating);
        }}
      />
    </section>
  );
}
