import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import type { Booking, BookingAction } from '../../api/agenda';
import { agendaApi, teamApi } from '../../api/runtime';
import { ApiError } from '../../api/client';
import { queryKeys } from '../../api/queryKeys';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select, Textarea } from '../../components/ui/Field';
import { formatDateISO, formatDateTime } from '../../lib/dates';
import { BOOKING_STATUS_LABELS, formatMoney } from '../../lib/format';

type Props = {
  booking: Booking | null;
  timezone: string;
  canWrite: boolean;
  onClose: () => void;
  onChanged: (booking: Booking) => void;
};

const ACTIVE_STATUSES = ['scheduled', 'confirmed'];

function messageOf(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

export function BookingDetailDialog({ booking, timezone, canWrite, onClose, onChanged }: Props) {
  const { company } = useAuth();
  const companyId = company?.id ?? '';
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [cancelMode, setCancelMode] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [rescheduleOpen, setRescheduleOpen] = useState(false);
  const [rescheduleDate, setRescheduleDate] = useState('');
  const [rescheduleWorker, setRescheduleWorker] = useState('');
  const [rescheduleReason, setRescheduleReason] = useState('');
  const [rescheduleSlot, setRescheduleSlot] = useState<string | null>(null);
  const [rescheduleError, setRescheduleError] = useState<string | null>(null);

  useEffect(() => {
    if (!booking) return;
    setNotes(booking.notes);
    setActionError(null);
    setCancelMode(false);
    setCancelReason('');
    setRescheduleOpen(false);
    setRescheduleDate(formatDateISO(booking.start_at, timezone));
    setRescheduleWorker(booking.worker);
    setRescheduleReason('');
    setRescheduleSlot(null);
    setRescheduleError(null);
  }, [booking, timezone]);

  const workersQuery = useQuery({
    queryKey: queryKeys.workers(companyId, { branch: booking?.branch, active: true }),
    queryFn: () => teamApi.workers.list({ branch: booking?.branch, active: true, page: 1 }),
    enabled: Boolean(booking && rescheduleOpen && companyId),
  });

  const availabilityQuery = useQuery({
    queryKey: queryKeys.availability(companyId, {
      branch: booking?.branch ?? '',
      service: booking?.service ?? '',
      worker: rescheduleWorker,
      date: rescheduleDate,
    }),
    queryFn: () =>
      agendaApi.availability({
        branch: booking?.branch ?? '',
        service: booking?.service ?? '',
        worker: rescheduleWorker,
        date: rescheduleDate,
      }),
    enabled: Boolean(booking && rescheduleOpen && companyId && rescheduleDate && rescheduleWorker),
  });

  if (!booking) {
    // Se mantiene montado para que el Dialog pueda devolver el foco al cerrar.
    return (
      <Dialog open={false} onOpenChange={() => onClose()} title="Detalle de reserva">
        <span />
      </Dialog>
    );
  }

  const active = ACTIVE_STATUSES.includes(booking.status);
  const editable = canWrite && active;

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ['bookings', companyId] });
    void queryClient.invalidateQueries({ queryKey: ['availability', companyId] });
  }

  async function runAction(action: BookingAction, reason = '') {
    setBusyAction(action);
    setActionError(null);
    try {
      const updated = await agendaApi.transitionBooking(booking!.id, action, reason);
      invalidate();
      onChanged(updated);
      setCancelMode(false);
      setCancelReason('');
    } catch (error) {
      setActionError(messageOf(error, 'No se pudo actualizar la reserva.'));
    } finally {
      setBusyAction(null);
    }
  }

  async function saveNotes() {
    setBusyAction('notes');
    setActionError(null);
    try {
      const updated = await agendaApi.updateNotes(booking!.id, notes);
      invalidate();
      onChanged(updated);
    } catch (error) {
      setActionError(messageOf(error, 'No se pudieron guardar las notas.'));
    } finally {
      setBusyAction(null);
    }
  }

  async function reschedule() {
    if (!rescheduleSlot) {
      setRescheduleError('Selecciona un horario disponible.');
      return;
    }
    setBusyAction('reschedule');
    setRescheduleError(null);
    try {
      const updated = await agendaApi.rescheduleBooking(booking!.id, {
        start_at: rescheduleSlot,
        worker: rescheduleWorker,
        reason: rescheduleReason.trim(),
      });
      invalidate();
      onChanged(updated);
      setRescheduleOpen(false);
      setRescheduleSlot(null);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setRescheduleSlot(null);
        setRescheduleError(error.message);
        void availabilityQuery.refetch();
        return;
      }
      setRescheduleError(messageOf(error, 'No se pudo reprogramar la reserva.'));
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Detalle de reserva"
      description={`${booking.service_name} · ${booking.customer_name}`}
      wide
      footer={
        <Button variant="secondary" onClick={onClose}>
          Cerrar
        </Button>
      }
    >
      {actionError ? <ErrorBanner message={actionError} /> : null}

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-muted">Inicio</dt>
          <dd className="text-ink">{formatDateTime(booking.start_at, timezone)}</dd>
        </div>
        <div>
          <dt className="text-muted">Fin</dt>
          <dd className="text-ink">{formatDateTime(booking.end_at, timezone)}</dd>
        </div>
        <div>
          <dt className="text-muted">Trabajador</dt>
          <dd className="text-ink">{booking.worker_name}</dd>
        </div>
        <div>
          <dt className="text-muted">Sucursal</dt>
          <dd className="text-ink">{booking.branch_name}</dd>
        </div>
        <div>
          <dt className="text-muted">Precio</dt>
          <dd className="text-ink">{formatMoney(booking.price)}</dd>
        </div>
        <div>
          <dt className="text-muted">Estado</dt>
          <dd>
            <Badge tone={booking.status}>{BOOKING_STATUS_LABELS[booking.status]}</Badge>
          </dd>
        </div>
      </dl>

      {canWrite ? (
        <div className="mt-4">
          <Field label="Notas" htmlFor="booking-detail-notes">
            <Textarea
              id="booking-detail-notes"
              rows={2}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </Field>
          <Button
            className="mt-2"
            variant="secondary"
            loading={busyAction === 'notes'}
            loadingLabel="Guardando…"
            onClick={() => void saveNotes()}
          >
            Guardar notas
          </Button>
        </div>
      ) : (
        <p className="mt-4 text-sm text-ink">
          <span className="text-muted">Notas: </span>
          {booking.notes || 'Sin notas'}
        </p>
      )}

      {editable ? (
        <section className="mt-6 space-y-3 border-t border-line pt-4">
          <h3 className="text-sm font-semibold text-ink">Acciones</h3>
          <div className="flex flex-wrap gap-2">
            {booking.status === 'scheduled' ? (
              <Button loading={busyAction === 'confirm'} onClick={() => void runAction('confirm')}>
                Confirmar
              </Button>
            ) : null}
            <Button
              variant="secondary"
              loading={busyAction === 'complete'}
              onClick={() => void runAction('complete')}
            >
              Completar
            </Button>
            <Button
              variant="secondary"
              loading={busyAction === 'no-show'}
              onClick={() => void runAction('no-show')}
            >
              No asistió
            </Button>
            <Button variant="danger" onClick={() => setCancelMode((value) => !value)}>
              Cancelar reserva
            </Button>
            <Button variant="secondary" onClick={() => setRescheduleOpen((value) => !value)}>
              Reprogramar
            </Button>
          </div>

          {cancelMode ? (
            <div className="rounded-md border border-danger/40 bg-danger-soft/40 p-3">
              <Field label="Motivo de cancelación" htmlFor="booking-cancel-reason">
                <Input
                  id="booking-cancel-reason"
                  value={cancelReason}
                  onChange={(event) => setCancelReason(event.target.value)}
                />
              </Field>
              <Button
                className="mt-2"
                variant="danger"
                loading={busyAction === 'cancel'}
                onClick={() => void runAction('cancel', cancelReason)}
              >
                Confirmar cancelación
              </Button>
            </div>
          ) : null}

          {rescheduleOpen ? (
            <div className="rounded-md border border-line bg-surface p-3">
              {rescheduleError ? <ErrorBanner message={rescheduleError} /> : null}
              <div className="mt-2 grid gap-3 sm:grid-cols-2">
                <Field label="Nuevo día" htmlFor="booking-reschedule-date">
                  <Input
                    id="booking-reschedule-date"
                    type="date"
                    value={rescheduleDate}
                    onChange={(event) => {
                      setRescheduleDate(event.target.value);
                      setRescheduleSlot(null);
                    }}
                  />
                </Field>
                <Field label="Trabajador para reprogramar" htmlFor="booking-reschedule-worker">
                  <Select
                    id="booking-reschedule-worker"
                    value={rescheduleWorker}
                    onChange={(event) => {
                      setRescheduleWorker(event.target.value);
                      setRescheduleSlot(null);
                    }}
                  >
                    {(workersQuery.data?.results ?? []).length === 0 ? (
                      <option value={booking.worker}>{booking.worker_name}</option>
                    ) : (
                      (workersQuery.data?.results ?? []).map((worker) => (
                        <option key={worker.id} value={worker.id}>
                          {worker.display_name}
                        </option>
                      ))
                    )}
                  </Select>
                </Field>
                <Field label="Motivo de reprogramación" htmlFor="booking-reschedule-reason">
                  <Input
                    id="booking-reschedule-reason"
                    value={rescheduleReason}
                    onChange={(event) => setRescheduleReason(event.target.value)}
                  />
                </Field>
              </div>

              <div className="mt-3">
                {availabilityQuery.isError ? (
                  <ErrorBanner
                    message={
                      availabilityQuery.error instanceof Error
                        ? availabilityQuery.error.message
                        : 'No se pudo consultar la disponibilidad.'
                    }
                    onRetry={() => void availabilityQuery.refetch()}
                  />
                ) : availabilityQuery.isLoading ? (
                  <p className="text-sm text-muted">Consultando disponibilidad…</p>
                ) : (availabilityQuery.data?.slots.length ?? 0) === 0 ? (
                  <p className="text-sm text-muted">No hay cupos disponibles ese día.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {availabilityQuery.data?.slots.map((item) => (
                      <button
                        key={item.start_at}
                        type="button"
                        aria-pressed={rescheduleSlot === item.start_at}
                        onClick={() => setRescheduleSlot(item.start_at)}
                        className={`rounded-md border px-3 py-1.5 text-sm ${
                          rescheduleSlot === item.start_at
                            ? 'border-brand bg-brand-soft text-brand'
                            : 'border-line bg-panel text-ink'
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <Button
                className="mt-3"
                loading={busyAction === 'reschedule'}
                onClick={() => void reschedule()}
              >
                Reprogramar reserva
              </Button>
            </div>
          ) : null}
        </section>
      ) : null}
    </Dialog>
  );
}
