import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { teamApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import type { Worker } from '../../api/team';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select } from '../../components/ui/Field';
import { Pagination } from '../../components/ui/Pagination';
import { Skeleton } from '../../components/ui/Skeleton';
import { useDebouncedValue } from '../../lib/useDebouncedValue';
import { WorkerFormDialog } from './WorkerFormDialog';

export function WorkersSection({
  onManageSchedule,
}: {
  onManageSchedule: (worker: Worker) => void;
}) {
  const { company, bootstrap, can } = useAuth();
  const queryClient = useQueryClient();
  const canWrite = can('workforce.write');

  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);
  const [activeFilter, setActiveFilter] = useState<'' | 'true' | 'false'>('');
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Worker | null>(null);

  const params = {
    search: debouncedSearch || undefined,
    active: activeFilter === '' ? undefined : activeFilter === 'true',
    page,
    ordering: 'last_name',
  };

  const query = useQuery({
    queryKey: queryKeys.workers(company?.id ?? '', params),
    queryFn: () => teamApi.workers.list(params),
    enabled: Boolean(company),
  });

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(worker: Worker) {
    setEditing(worker);
    setFormOpen(true);
  }

  function branchLabel(worker: Worker) {
    return worker.branches
      .map((id) => bootstrap?.branches.find((branch) => branch.id === id)?.name ?? 'Sucursal')
      .join(', ');
  }

  const workers = query.data?.results ?? [];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div className="grid flex-1 gap-3 sm:grid-cols-[1fr_12rem]">
          <Field label="Buscar" htmlFor="worker-search">
            <Input
              id="worker-search"
              type="search"
              placeholder="Nombre, correo o cargo"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
            />
          </Field>
          <Field label="Estado" htmlFor="worker-active">
            <Select
              id="worker-active"
              value={activeFilter}
              onChange={(event) => {
                setActiveFilter(event.target.value as '' | 'true' | 'false');
                setPage(1);
              }}
            >
              <option value="">Todos</option>
              <option value="true">Activos</option>
              <option value="false">Inactivos</option>
            </Select>
          </Field>
        </div>
        {canWrite ? <Button onClick={openCreate}>Nuevo trabajador</Button> : null}
      </div>

      {query.isError ? (
        <ErrorBanner
          message="No se pudieron cargar los trabajadores."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {query.isPending ? <Skeleton rows={4} /> : null}

      {query.isSuccess && workers.length === 0 ? (
        <EmptyState
          title="Sin trabajadores"
          description={
            debouncedSearch || activeFilter
              ? 'No hay trabajadores que coincidan con los filtros.'
              : 'Crea el primer trabajador y define su horario para abrir cupos.'
          }
          action={canWrite ? <Button onClick={openCreate}>Nuevo trabajador</Button> : undefined}
        />
      ) : null}

      {workers.length > 0 ? (
        <>
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3">Trabajador</th>
                  <th scope="col" className="px-4 py-3">Contacto</th>
                  <th scope="col" className="px-4 py-3">Sucursales</th>
                  <th scope="col" className="px-4 py-3">Estado</th>
                  <th scope="col" className="px-4 py-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {workers.map((worker) => (
                  <tr key={worker.id}>
                    <td className="whitespace-nowrap px-4 py-3">
                      <span className="flex items-center gap-2 font-medium text-ink">
                        <span
                          aria-hidden
                          className="h-2.5 w-2.5 rounded-full"
                          style={{ backgroundColor: worker.color }}
                        />
                        {worker.display_name}
                      </span>
                      {worker.job_title ? (
                        <span className="block text-xs text-muted">{worker.job_title}</span>
                      ) : null}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-muted">
                      <span className="block">{worker.email || 'Sin correo'}</span>
                      <span className="block text-xs">{worker.phone || 'Sin teléfono'}</span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-muted">{branchLabel(worker) || '—'}</td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <Badge tone={worker.active ? 'active' : 'inactive'}>
                        {worker.active ? 'Activo' : 'Inactivo'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap justify-end gap-1">
                        <Button variant="ghost" onClick={() => onManageSchedule(worker)}>
                          Horario
                        </Button>
                        {canWrite ? (
                          <Button variant="ghost" onClick={() => openEdit(worker)}>
                            Editar
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} count={query.data?.count ?? 0} onPage={setPage} />
        </>
      ) : null}

      {formOpen ? (
        <WorkerFormDialog
          open
          worker={editing}
          onOpenChange={(next) => {
            if (!next) setFormOpen(false);
          }}
          onSaved={() => {
            void queryClient.invalidateQueries({ queryKey: ['workers', company?.id ?? ''] });
          }}
        />
      ) : null}
    </div>
  );
}
