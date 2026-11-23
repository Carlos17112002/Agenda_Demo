import { useQuery } from '@tanstack/react-query';

import type { Customer } from '../../api/customers';
import { agendaApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Dialog } from '../../components/ui/Dialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Skeleton } from '../../components/ui/Skeleton';
import { formatDateTime } from '../../lib/dates';

export function CustomerHistoryDialog({
  customer,
  onClose,
}: {
  customer: Customer | null;
  onClose: () => void;
}) {
  const { company, bootstrap } = useAuth();
  const query = useQuery({
    queryKey: queryKeys.customerBookings(company?.id ?? '', customer?.id ?? ''),
    queryFn: () =>
      agendaApi.listBookings({ customer: customer!.id, ordering: '-start_at', page: 1 }),
    enabled: Boolean(company && customer),
  });

  if (!customer) {
    // Se mantiene montado para que el Dialog pueda devolver el foco al cerrar.
    return (
      <Dialog open={false} onOpenChange={() => onClose()} title="Historial de reservas">
        <span />
      </Dialog>
    );
  }

  const timezoneFor = (branchId: string) =>
    bootstrap?.branches.find((branch) => branch.id === branchId)?.timezone ?? 'America/Santiago';

  const bookings = query.data?.results ?? [];

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={`Historial de ${customer.display_name}`}
      description="Últimas reservas registradas para este cliente."
      wide
    >
      {query.isPending ? <Skeleton rows={3} /> : null}
      {query.isError ? (
        <ErrorBanner
          message="No se pudo cargar el historial."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {query.isSuccess && bookings.length === 0 ? (
        <EmptyState
          title="Sin reservas"
          description="Este cliente todavía no tiene reservas registradas."
        />
      ) : null}
      {bookings.length > 0 ? (
        <>
          <ul className="divide-y divide-line">
            {bookings.map((booking) => (
              <li
                key={booking.id}
                className="flex flex-wrap items-center justify-between gap-2 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-ink">{booking.service_name}</p>
                  <p className="text-xs text-muted">
                    {formatDateTime(booking.start_at, timezoneFor(booking.branch))} ·{' '}
                    {booking.worker_name}
                  </p>
                </div>
                <Badge tone={booking.status}>{booking.status_display}</Badge>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-muted">
            {query.data && query.data.count > bookings.length
              ? `Se muestran las últimas ${bookings.length} de ${query.data.count} reservas.`
              : `${bookings.length} reservas en total.`}
          </p>
        </>
      ) : null}
    </Dialog>
  );
}
