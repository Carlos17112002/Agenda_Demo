import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError } from '../../api/client';
import { teamApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import type { Paginated } from '../../api/types';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/Dialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Select } from '../../components/ui/Field';
import { Skeleton } from '../../components/ui/Skeleton';
import { formatDateTime, formatTime } from '../../lib/dates';
import { ExceptionDialog } from './ExceptionDialog';

type ExceptionItem = {
  id: string;
  worker: string;
  branch: string | null;
  starts_at: string;
  ends_at: string;
  reason: string;
};

type ExceptionRecord = {
  id: string;
  label: string;
};

type ExceptionsApi = {
  list: (params?: { worker?: string; page?: number }) => Promise<Paginated<ExceptionItem>>;
  create: (input: {
    worker: string;
    branch: string | null;
    starts_at: string;
    ends_at: string;
    reason: string;
  }) => Promise<ExceptionItem>;
  remove: (id: string) => Promise<void>;
};

const CONFIG = {
  timeOff: {
    title: 'Ausencias',
    description: 'Vacaciones, licencias y permisos que quitan cupos en la agenda.',
    addLabel: 'Nueva ausencia',
    emptyTitle: 'Sin ausencias',
    emptyDescription: 'No hay ausencias registradas para este trabajador.',
    dialogTitle: 'Eliminar ausencia',
    apiPath: 'time-off',
  },
  blocked: {
    title: 'Bloqueos',
    description: 'Bloqueos puntuales de la agenda del trabajador.',
    addLabel: 'Nuevo bloqueo',
    emptyTitle: 'Sin bloqueos',
    emptyDescription: 'No hay bloqueos registrados para este trabajador.',
    dialogTitle: 'Eliminar bloqueo',
    apiPath: 'blocked-slots',
  },
} as const;

export function ExceptionsSection({
  kind,
  workerId,
  onWorkerChange,
}: {
  kind: 'timeOff' | 'blocked';
  workerId: string;
  onWorkerChange: (workerId: string) => void;
}) {
  const { company, bootstrap, can } = useAuth();
  const queryClient = useQueryClient();
  const canWrite = can('workforce.write');
  const config = CONFIG[kind];

  const [dialogOpen, setDialogOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<ExceptionRecord | null>(null);

  const workersQuery = useQuery({
    queryKey: queryKeys.workers(company?.id ?? '', { active: true, page: 1 }),
    queryFn: () => teamApi.workers.list({ active: true, page: 1 }),
    enabled: Boolean(company),
  });
  const workers = workersQuery.data?.results ?? [];
  const selectedWorkerId = workerId || workers[0]?.id || '';

  const api = (kind === 'timeOff' ? teamApi.timeOff : teamApi.blockedSlots) as ExceptionsApi;
  const keyFactory = kind === 'timeOff' ? queryKeys.timeOff : queryKeys.blockedSlots;

  const query = useQuery({
    queryKey: keyFactory(company?.id ?? '', selectedWorkerId),
    queryFn: () => api.list({ worker: selectedWorkerId, page: 1 }),
    enabled: Boolean(company && selectedWorkerId),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.remove(id),
    onSuccess: () => {
      setPendingDelete(null);
      void queryClient.invalidateQueries({
        queryKey: [config.apiPath, company?.id ?? ''],
      });
    },
  });

  const timezoneFor = (branchId: string | null) => {
    if (!branchId) return bootstrap?.branches[0]?.timezone ?? 'America/Santiago';
    return (
      bootstrap?.branches.find((branch) => branch.id === branchId)?.timezone ??
      'America/Santiago'
    );
  };
  const branchName = (branchId: string | null) =>
    branchId
      ? bootstrap?.branches.find((branch) => branch.id === branchId)?.name ?? 'Sucursal'
      : 'Todas las sucursales';

  const items = query.data?.results ?? [];
  const removeError =
    remove.error instanceof ApiError
      ? remove.error.message
      : remove.error
        ? 'No se pudo eliminar el registro.'
        : null;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <Field label="Trabajador" htmlFor={`${kind}-worker`} className="w-full sm:w-72">
          <Select
            id={`${kind}-worker`}
            value={selectedWorkerId}
            onChange={(event) => onWorkerChange(event.target.value)}
          >
            {workers.map((worker) => (
              <option key={worker.id} value={worker.id}>
                {worker.display_name}
              </option>
            ))}
          </Select>
        </Field>
        {canWrite && selectedWorkerId ? (
          <Button onClick={() => setDialogOpen(true)}>{config.addLabel}</Button>
        ) : null}
      </div>

      <p className="mb-4 text-sm text-muted">{config.description}</p>

      {removeError ? <ErrorBanner message={removeError} /> : null}
      {query.isError ? (
        <ErrorBanner
          message={`No se pudieron cargar ${config.title.toLowerCase()}.`}
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {workersQuery.isPending || query.isPending ? <Skeleton rows={3} /> : null}

      {!workersQuery.isPending && workers.length === 0 ? (
        <EmptyState
          title="Sin trabajadores"
          description="Crea un trabajador en la pestaña Trabajadores para registrar este tipo de bloqueo."
        />
      ) : null}

      {query.isSuccess && items.length === 0 ? (
        <EmptyState title={config.emptyTitle} description={config.emptyDescription} />
      ) : null}

      {items.length > 0 ? (
        <ul className="divide-y divide-line rounded-lg border border-line bg-panel">
          {items.map((item) => {
            const timezone = timezoneFor(item.branch);
            return (
              <li
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-2 p-4 text-sm"
              >
                <div>
                  <p className="font-medium text-ink">
                    {formatDateTime(item.starts_at, timezone)} –{' '}
                    {formatTime(item.ends_at, timezone)}
                  </p>
                  <p className="text-xs text-muted">
                    {branchName(item.branch)} · {item.reason || 'Sin motivo'}
                  </p>
                </div>
                {canWrite ? (
                  <Button
                    variant="ghost"
                    aria-label={`Eliminar ${kind === 'timeOff' ? 'ausencia' : 'bloqueo'} ${item.reason || 'sin motivo'}`}
                    onClick={() =>
                      setPendingDelete({
                        id: item.id,
                        label: `${formatDateTime(item.starts_at, timezone)} – ${formatTime(item.ends_at, timezone)}`,
                      })
                    }
                  >
                    Eliminar
                  </Button>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}

      {dialogOpen ? (
        <ExceptionDialog
          kind={kind}
          workerId={selectedWorkerId}
          onOpenChange={(next) => {
            if (!next) setDialogOpen(false);
          }}
          onSaved={() => {
            void queryClient.invalidateQueries({
              queryKey: [config.apiPath, company?.id ?? ''],
            });
          }}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        onOpenChange={(next) => {
          if (!next) setPendingDelete(null);
        }}
        title={config.dialogTitle}
        description={
          pendingDelete
            ? `Se quitará el registro ${pendingDelete.label}. Los cupos volverán a estar disponibles.`
            : ''
        }
        confirmLabel="Eliminar"
        loading={remove.isPending}
        onConfirm={() => {
          if (pendingDelete) remove.mutate(pendingDelete.id);
        }}
      />
    </div>
  );
}

export function TimeOffSection(props: {
  workerId: string;
  onWorkerChange: (workerId: string) => void;
}) {
  return <ExceptionsSection kind="timeOff" {...props} />;
}

export function BlockedSlotsSection(props: {
  workerId: string;
  onWorkerChange: (workerId: string) => void;
}) {
  return <ExceptionsSection kind="blocked" {...props} />;
}
