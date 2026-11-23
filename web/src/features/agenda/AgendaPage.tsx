import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';

import type { Booking, BookingListParams, BookingStatus } from '../../api/agenda';
import { agendaApi, servicesApi, teamApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { PageHeader } from '../../components/ui/PageHeader';
import { Pagination } from '../../components/ui/Pagination';
import { Skeleton } from '../../components/ui/Skeleton';
import { todayInZone, weekRange, shiftDate, formatDateLabel } from '../../lib/dates';
import { AgendaCalendar } from './AgendaCalendar';
import { BookingCreateDialog } from './BookingCreateDialog';
import { workersForColumns, type CalendarSlot } from './agendaLayout';
import { BookingDetailDialog } from './BookingDetailDialog';
import { pickInitialBranchId } from './branchSelection';

const STATUS_OPTIONS: { value: BookingStatus | ''; label: string }[] = [
  { value: '', label: 'Todos los estados' },
  { value: 'scheduled', label: 'Agendadas' },
  { value: 'confirmed', label: 'Confirmadas' },
  { value: 'completed', label: 'Completadas' },
  { value: 'canceled', label: 'Canceladas' },
  { value: 'no_show', label: 'No asistió' },
];

async function fetchBranchWorkingHours(branchId: string) {
  const first = await teamApi.workingHours.list({ branch: branchId, page: 1 });
  const results = [...first.results];
  const pages = Math.ceil(first.count / 50);
  if (pages > 1) {
    const rest = await Promise.all(
      Array.from({ length: pages - 1 }, (_, index) =>
        teamApi.workingHours.list({ branch: branchId, page: index + 2 }),
      ),
    );
    rest.forEach((page) => results.push(...page.results));
  }
  return results;
}

export function AgendaPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [initialSlot, setInitialSlot] = useState<CalendarSlot | null>(null);
  const { company, bootstrap, can } = useAuth();
  const branches = useMemo(
    () => (bootstrap?.branches ?? []).filter((branch) => branch.active),
    [bootstrap],
  );
  const [branchId, setBranchId] = useState(() =>
    pickInitialBranchId(branches, bootstrap?.membership.default_branch?.id ?? null),
  );
  const preferredBranchId = bootstrap?.membership.default_branch?.id ?? null;
  useEffect(() => {
    if (!branches.some((item) => item.id === branchId)) {
      setBranchId(pickInitialBranchId(branches, preferredBranchId));
    }
  }, [branches, branchId, preferredBranchId]);
  const branch = branches.find((item) => item.id === branchId) ?? branches[0];
  const timezone = branch?.timezone ?? 'America/Santiago';

  const [view, setView] = useState<'day' | 'week'>('day');
  const [anchorDate, setAnchorDate] = useState(() => todayInZone(timezone));
  const [workerId, setWorkerId] = useState('');
  const [serviceId, setServiceId] = useState('');
  const [status, setStatus] = useState<BookingStatus | ''>('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Booking | null>(null);

  const workersQuery = useQuery({
    queryKey: queryKeys.workers(company?.id ?? '', { branch: branchId, active: true }),
    queryFn: () => teamApi.workers.list({ branch: branchId, active: true, page: 1 }),
    enabled: Boolean(company && branchId),
  });
  const servicesQuery = useQuery({
    queryKey: queryKeys.services(company?.id ?? '', { active: true }),
    queryFn: () => servicesApi.list({ active: true, page: 1 }),
    enabled: Boolean(company && branchId),
  });

  const range = view === 'day' ? { date: anchorDate } : weekRange(anchorDate);
  const params: BookingListParams = {
    branch: branchId,
    ...range,
    worker: workerId || undefined,
    service: serviceId || undefined,
    status: status || undefined,
    page,
    ordering: 'start_at',
  };
  const bookingsQuery = useQuery({
    queryKey: queryKeys.bookings(company?.id ?? '', params),
    queryFn: () => agendaApi.listBookings(params),
    enabled: Boolean(company && branchId),
  });
  const shiftsQuery = useQuery({
    queryKey: queryKeys.branchWorkingHours(company?.id ?? '', branchId),
    queryFn: () => fetchBranchWorkingHours(branchId),
    enabled: Boolean(company && branchId),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const shifts = shiftsQuery.data ?? [];

  const workers = workersQuery.data?.results ?? [];
  const services = servicesQuery.data?.results ?? [];
  const branchServices = services.filter(
    (service) => service.branches.length === 0 || service.branches.includes(branchId),
  );
  const bookings = bookingsQuery.data?.results ?? [];
  const columns = workersForColumns(workers, workerId);

  function changeBranch(nextBranchId: string) {
    setBranchId(nextBranchId);
    const nextBranch = branches.find((item) => item.id === nextBranchId);
    setAnchorDate(todayInZone(nextBranch?.timezone ?? timezone));
    setWorkerId('');
    setServiceId('');
    setStatus('');
    setPage(1);
  }

  function moveDate(days: number) {
    setAnchorDate((current) => shiftDate(current, view === 'day' ? days : days * 7));
    setPage(1);
  }

  function changeView(next: 'day' | 'week') {
    setView(next);
    setPage(1);
  }

  const periodLabel =
    view === 'day'
      ? formatDateLabel(anchorDate)
      : `${formatDateLabel(weekRange(anchorDate).date_from)} – ${formatDateLabel(weekRange(anchorDate).date_to)}`;

  if (branches.length === 0) {
    return (
      <EmptyState
        title="No hay sucursales activas"
        description="La agenda necesita una sucursal activa con zona horaria configurada."
      />
    );
  }

  return (
    <section>
      <PageHeader
        title="Agenda"
        description={`Horarios en ${timezone} · ${periodLabel}`}
        actions={
          can('bookings.write') ? (
            <Button
              onClick={() => {
                setInitialSlot(null);
                setCreateOpen(true);
              }}
            >
              Nueva reserva
            </Button>
          ) : null
        }
      />

      <div className="mb-4 flex flex-wrap items-end gap-2">
        <label className="text-sm text-muted">
          Sucursal
          <select
            className="mt-1 block rounded-md border border-line bg-panel px-2 py-1.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
            value={branchId}
            onChange={(event) => changeBranch(event.target.value)}
          >
            {branches.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-muted">
          Trabajador
          <select
            className="mt-1 block rounded-md border border-line bg-panel px-2 py-1.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
            value={workerId}
            onChange={(event) => {
              setWorkerId(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Todos</option>
            {workers.map((worker) => (
              <option key={worker.id} value={worker.id}>
                {worker.display_name}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-muted">
          Servicio
          <select
            className="mt-1 block rounded-md border border-line bg-panel px-2 py-1.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
            value={serviceId}
            onChange={(event) => {
              setServiceId(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Todos</option>
            {branchServices.map((service) => (
              <option key={service.id} value={service.id}>
                {service.name}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-muted">
          Estado
          <select
            className="mt-1 block rounded-md border border-line bg-panel px-2 py-1.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as BookingStatus | '');
              setPage(1);
            }}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Vista" className="flex rounded-md border border-line bg-panel">
            <Button variant={view === 'day' ? 'primary' : 'ghost'} onClick={() => changeView('day')}>
              Día
            </Button>
            <Button variant={view === 'week' ? 'primary' : 'ghost'} onClick={() => changeView('week')}>
              Semana
            </Button>
          </div>
          <Button variant="secondary" onClick={() => moveDate(-1)}>
            Anterior
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              setAnchorDate(todayInZone(timezone));
              setPage(1);
            }}
          >
            Hoy
          </Button>
          <Button variant="secondary" onClick={() => moveDate(1)}>
            Siguiente
          </Button>
        </div>
      </div>

      {bookingsQuery.isError ? (
        <ErrorBanner
          message={bookingsQuery.error instanceof Error ? bookingsQuery.error.message : 'No se pudo cargar la agenda.'}
          onRetry={() => void bookingsQuery.refetch()}
        />
      ) : null}

      <div className="mt-4">
        {workersQuery.isLoading || bookingsQuery.isLoading ? (
          <Skeleton rows={6} />
        ) : (
          <AgendaCalendar
            view={view}
            anchorDate={anchorDate}
            dateFrom={weekRange(anchorDate).date_from}
            timezone={timezone}
            workers={columns}
            bookings={bookings}
            shifts={shifts}
            onSelectBooking={setSelected}
            onSelectSlot={
              can('bookings.write')
                ? (slot) => {
                    setInitialSlot(slot);
                    setCreateOpen(true);
                  }
                : undefined
            }
          />
        )}
        {shiftsQuery.isError ? (
          <p className="mt-2 text-xs text-muted">
            No se pudieron cargar los horarios de atención; el eje usa 08:00–20:00.
          </p>
        ) : null}
      </div>

      {bookingsQuery.data ? (
        <Pagination page={page} count={bookingsQuery.data.count} onPage={setPage} />
      ) : null}

      <BookingCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        defaultBranchId={branchId}
        defaultDate={anchorDate}
        initialSlot={initialSlot}
        onCreated={() => {
          void queryClient.invalidateQueries({ queryKey: ['bookings', company?.id] });
          setCreateOpen(false);
        }}
      />

      <BookingDetailDialog
        booking={selected}
        timezone={timezone}
        canWrite={can('bookings.write')}
        onClose={() => setSelected(null)}
        onChanged={(updated) => {
          setSelected(updated);
          void queryClient.invalidateQueries({ queryKey: ['bookings', company?.id] });
          void queryClient.invalidateQueries({ queryKey: ['availability', company?.id] });
        }}
      />
    </section>
  );
}
