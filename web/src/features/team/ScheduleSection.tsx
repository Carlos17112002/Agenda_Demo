import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError } from '../../api/client';
import { teamApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import type { Break, WorkingHours } from '../../api/team';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/Dialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Select } from '../../components/ui/Field';
import { Skeleton } from '../../components/ui/Skeleton';
import { weekdayLabel } from '../../lib/format';
import { ScheduleSlotDialog } from './ScheduleSlotDialog';

type PendingDelete = { kind: 'hours' | 'break'; id: string; label: string };

function slotLabel(slot: WorkingHours | Break) {
  return `${weekdayLabel(slot.weekday)} · ${slot.start_time.slice(0, 5)} – ${slot.end_time.slice(0, 5)}`;
}

export function ScheduleSection({
  workerId,
  onWorkerChange,
}: {
  workerId: string;
  onWorkerChange: (workerId: string) => void;
}) {
  const { company, bootstrap, can } = useAuth();
  const queryClient = useQueryClient();
  const canWrite = can('workforce.write');

  const [dialogKind, setDialogKind] = useState<'hours' | 'break' | null>(null);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);

  const workersQuery = useQuery({
    queryKey: queryKeys.workers(company?.id ?? '', { active: true, page: 1 }),
    queryFn: () => teamApi.workers.list({ active: true, page: 1 }),
    enabled: Boolean(company),
  });
  const workers = workersQuery.data?.results ?? [];
  const selectedWorkerId = workerId || workers[0]?.id || '';
  const selectedWorker = workers.find((worker) => worker.id === selectedWorkerId);

  const hoursQuery = useQuery({
    queryKey: queryKeys.workingHours(company?.id ?? '', selectedWorkerId),
    queryFn: () => teamApi.workingHours.list({ worker: selectedWorkerId, page: 1 }),
    enabled: Boolean(company && selectedWorkerId),
  });
  const breaksQuery = useQuery({
    queryKey: queryKeys.breaks(company?.id ?? '', selectedWorkerId),
    queryFn: () => teamApi.breaks.list({ worker: selectedWorkerId, page: 1 }),
    enabled: Boolean(company && selectedWorkerId),
  });

  const remove = useMutation({
    mutationFn: (pending: PendingDelete) =>
      pending.kind === 'hours'
        ? teamApi.workingHours.remove(pending.id)
        : teamApi.breaks.remove(pending.id),
    onSuccess: () => {
      setPendingDelete(null);
      void queryClient.invalidateQueries({ queryKey: ['working-hours', company?.id ?? ''] });
      void queryClient.invalidateQueries({ queryKey: ['breaks', company?.id ?? ''] });
    },
  });

  function invalidateSchedule() {
    void queryClient.invalidateQueries({ queryKey: ['working-hours', company?.id ?? ''] });
    void queryClient.invalidateQueries({ queryKey: ['breaks', company?.id ?? ''] });
  }

  const branchIds = selectedWorker?.branches ?? [];
  const branches = (bootstrap?.branches ?? []).filter(
    (branch) => branchIds.length === 0 || branchIds.includes(branch.id),
  );
  const hours = hoursQuery.data?.results ?? [];
  const breaks = breaksQuery.data?.results ?? [];
  const loading = workersQuery.isPending || hoursQuery.isPending || breaksQuery.isPending;
  const failed = workersQuery.isError || hoursQuery.isError || breaksQuery.isError;
  const removeError =
    remove.error instanceof ApiError
      ? remove.error.message
      : remove.error
        ? 'No se pudo eliminar el bloque.'
        : null;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <Field label="Trabajador" htmlFor="schedule-worker" className="w-full sm:w-72">
          <Select
            id="schedule-worker"
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
        {canWrite && selectedWorkerId && branches.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setDialogKind('break')}>
              Agregar pausa
            </Button>
            <Button onClick={() => setDialogKind('hours')}>Agregar horario</Button>
          </div>
        ) : null}
      </div>

      {removeError ? <ErrorBanner message={removeError} /> : null}
      {failed ? (
        <ErrorBanner
          message="No se pudo cargar el horario."
          onRetry={() => {
            void workersQuery.refetch();
            void hoursQuery.refetch();
            void breaksQuery.refetch();
          }}
        />
      ) : null}
      {loading ? <Skeleton rows={3} /> : null}

      {!loading && workers.length === 0 ? (
        <EmptyState
          title="Sin trabajadores"
          description="Crea un trabajador en la pestaña Trabajadores antes de definir horarios."
        />
      ) : null}

      {!loading && selectedWorker && branches.length === 0 ? (
        <EmptyState
          title="Sin sucursales asignadas"
          description="Asigna al menos una sucursal al trabajador para definir su horario."
        />
      ) : null}

      <div className="space-y-4">
        {branches.map((branch) => {
          const branchHours = hours
            .filter((slot) => slot.branch === branch.id)
            .sort((a, b) => a.weekday - b.weekday || a.start_time.localeCompare(b.start_time));
          const branchBreaks = breaks
            .filter((slot) => slot.branch === branch.id)
            .sort((a, b) => a.weekday - b.weekday || a.start_time.localeCompare(b.start_time));

          return (
            <div key={branch.id} className="rounded-lg border border-line bg-panel p-4">
              <h2 className="text-base font-semibold text-ink">{branch.name}</h2>
              <div className="mt-3 grid gap-4 md:grid-cols-2">
                <div>
                  <h3 className="mb-2 text-sm font-medium text-ink">Turnos</h3>
                  {branchHours.length === 0 ? (
                    <p className="text-sm text-muted">Sin turnos.</p>
                  ) : (
                    <ul className="divide-y divide-line">
                      {branchHours.map((slot) => (
                        <li
                          key={slot.id}
                          className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"
                        >
                          <span className="text-ink">{slotLabel(slot)}</span>
                          {canWrite ? (
                            <Button
                              variant="ghost"
                              aria-label={`Eliminar ${weekdayLabel(slot.weekday)} ${slot.start_time.slice(0, 5)}`}
                              onClick={() =>
                                setPendingDelete({
                                  kind: 'hours',
                                  id: slot.id,
                                  label: slotLabel(slot),
                                })
                              }
                            >
                              Eliminar
                            </Button>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div>
                  <h3 className="mb-2 text-sm font-medium text-ink">Pausas</h3>
                  {branchBreaks.length === 0 ? (
                    <p className="text-sm text-muted">Sin pausas.</p>
                  ) : (
                    <ul className="divide-y divide-line">
                      {branchBreaks.map((slot) => (
                        <li
                          key={slot.id}
                          className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"
                        >
                          <span className="text-ink">
                            {slotLabel(slot)}
                            {slot.label ? (
                              <span className="ml-2 text-xs text-muted">{slot.label}</span>
                            ) : null}
                          </span>
                          {canWrite ? (
                            <Button
                              variant="ghost"
                              aria-label={`Eliminar pausa ${weekdayLabel(slot.weekday)} ${slot.start_time.slice(0, 5)}`}
                              onClick={() =>
                                setPendingDelete({
                                  kind: 'break',
                                  id: slot.id,
                                  label: slotLabel(slot),
                                })
                              }
                            >
                              Eliminar
                            </Button>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {dialogKind ? (
        <ScheduleSlotDialog
          kind={dialogKind}
          workerId={selectedWorkerId}
          branchIds={branchIds}
          onOpenChange={(next) => {
            if (!next) setDialogKind(null);
          }}
          onSaved={invalidateSchedule}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        onOpenChange={(next) => {
          if (!next) setPendingDelete(null);
        }}
        title={pendingDelete?.kind === 'break' ? 'Eliminar pausa' : 'Eliminar turno'}
        description={
          pendingDelete
            ? `Se quitará ${pendingDelete.label} del horario semanal. Las reservas existentes no se modifican.`
            : ''
        }
        confirmLabel="Eliminar"
        loading={remove.isPending}
        onConfirm={() => {
          if (pendingDelete) remove.mutate(pendingDelete);
        }}
      />
    </div>
  );
}
