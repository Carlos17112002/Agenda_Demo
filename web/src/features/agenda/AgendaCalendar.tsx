import type { Booking } from '../../api/agenda';
import type { Worker, WorkingHours } from '../../api/team';
import { formatDateLabel, formatTime } from '../../lib/dates';
import {
  CALENDAR_HOUR_HEIGHT,
  bookingBlockStyle,
  bookingsForWorker,
  groupWeek,
  hourBounds,
  overlapLanes,
  slotBlockStyle,
  slotStarts,
  timeLabel,
  weekdayIndex,
  type CalendarSlot,
} from './agendaLayout';

type Props = {
  view: 'day' | 'week';
  anchorDate: string;
  dateFrom: string;
  timezone: string;
  workers: Worker[];
  bookings: Booking[];
  shifts?: WorkingHours[];
  onSelectBooking: (booking: Booking) => void;
  onSelectSlot?: (slot: CalendarSlot) => void;
};

function workerColor(worker: Worker): string {
  return /^#[0-9A-Fa-f]{6}$/.test(worker.color) ? worker.color : 'var(--brand-primary)';
}

export function AgendaCalendar({
  view,
  anchorDate,
  dateFrom,
  timezone,
  workers,
  bookings,
  shifts = [],
  onSelectBooking,
  onSelectSlot,
}: Props) {
  if (view === 'week') {
    const days = groupWeek(bookings, dateFrom, timezone);
    const { startHour, endHour } = hourBounds(
      bookings,
      timezone,
      shifts,
      days.map((day) => weekdayIndex(day.date)),
    );
    const hours = Array.from(
      { length: endHour - startHour },
      (_, index) => startHour + index,
    );
    const slots = slotStarts(startHour, endHour);
    const gridHeight = (endHour - startHour) * CALENDAR_HOUR_HEIGHT;

    return (
      <div className="overflow-x-auto rounded-lg border border-line bg-panel">
        <div
          className="grid min-w-[940px] gap-px bg-line"
          style={{ gridTemplateColumns: '64px repeat(7, minmax(120px, 1fr))' }}
        >
          <div className="bg-panel p-2 text-xs font-semibold text-muted">Hora</div>
          {days.map((day) => (
            <h2
              key={day.date}
              className="bg-panel p-2 text-center text-sm font-semibold text-ink"
            >
              {formatDateLabel(day.date)}
            </h2>
          ))}

          <div className="relative bg-panel" style={{ height: gridHeight }}>
            {hours.map((hour, index) => (
              <span
                key={hour}
                className="absolute right-2 -translate-y-1/2 text-xs text-muted"
                style={{ top: index * CALENDAR_HOUR_HEIGHT }}
              >
                {String(hour).padStart(2, '0')}:00
              </span>
            ))}
          </div>

          {days.map((day) => {
            const { lanes, laneOf } = overlapLanes(day.bookings, timezone);
            return (
              <div key={day.date} className="relative bg-panel" style={{ height: gridHeight }}>
              {hours.map((hour, index) => (
                <span
                  key={hour}
                  aria-hidden="true"
                  className="absolute inset-x-0 border-t border-line/70"
                  style={{ top: index * CALENDAR_HOUR_HEIGHT }}
                />
              ))}
              {onSelectSlot
                ? slots.map((start) => (
                    <button
                      key={start}
                      type="button"
                      onClick={() =>
                        onSelectSlot({ date: day.date, time: timeLabel(start) })
                      }
                      aria-label={`Crear reserva el ${formatDateLabel(day.date)} a las ${timeLabel(start)}`}
                      className="absolute inset-x-0 z-0 transition hover:bg-surface focus-visible:bg-brand-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
                      style={slotBlockStyle(start, startHour, endHour)}
                    />
                  ))
                : null}
              {day.bookings.map((booking) => (
                <button
                  type="button"
                  key={booking.id}
                  onClick={() => onSelectBooking(booking)}
                  className="absolute z-10 overflow-hidden rounded-md border-l-4 bg-surface p-1.5 text-left text-xs transition hover:bg-brand-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
                  style={{
                    ...bookingBlockStyle(booking, startHour, endHour, timezone),
                    left: `calc(${((laneOf.get(booking.id) ?? 0) / lanes) * 100}% + 2px)`,
                    width: `calc(${100 / lanes}% - 4px)`,
                    borderLeftColor:
                      workers.length > 0
                        ? workerColor(
                            workers.find((worker) => worker.id === booking.worker) ?? workers[0],
                          )
                        : 'var(--brand-primary)',
                  }}
                >
                  <span className="block truncate font-semibold text-ink">
                    {formatTime(booking.start_at, timezone)} {booking.customer_name}
                  </span>
                  <span className="block truncate text-muted">{booking.service_name}</span>
                  <span className="sr-only">Ver reserva</span>
                </button>
              ))}
            </div>
            );
          })}
        </div>
      </div>
    );
  }

  const { startHour, endHour } = hourBounds(bookings, timezone, shifts, [
    weekdayIndex(anchorDate),
  ]);
  const hours = Array.from(
    { length: endHour - startHour },
    (_, index) => startHour + index,
  );
  const slots = slotStarts(startHour, endHour);
  const gridHeight = (endHour - startHour) * CALENDAR_HOUR_HEIGHT;
  const columns =
    workers.length > 0
      ? workers.map((worker) => ({
          id: worker.id,
          label: worker.display_name,
          color: workerColor(worker),
          bookings: bookingsForWorker(bookings, worker.id),
        }))
      : [
          {
            id: 'all',
            label: 'Agenda',
            color: 'var(--brand-primary)',
            bookings: [...bookings].sort((first, second) =>
              first.start_at.localeCompare(second.start_at),
            ),
          },
        ];

  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-panel">
      <div
        className="grid min-w-[640px] gap-px bg-line"
        style={{ gridTemplateColumns: `64px repeat(${columns.length}, minmax(140px, 1fr))` }}
      >
        <div className="bg-panel p-2 text-xs font-semibold text-muted">
          {formatDateLabel(anchorDate)}
        </div>
        {columns.map((column) => (
          <h2 key={column.id} className="bg-panel p-2 text-center text-sm font-semibold text-ink">
            {column.label}
          </h2>
        ))}

        <div className="relative bg-panel" style={{ height: gridHeight }}>
          {hours.map((hour, index) => (
            <span
              key={hour}
              className="absolute right-2 -translate-y-1/2 text-xs text-muted"
              style={{ top: index * CALENDAR_HOUR_HEIGHT }}
            >
              {String(hour).padStart(2, '0')}:00
            </span>
          ))}
        </div>

        {columns.map((column) => {
          return (
            <div key={column.id} className="relative bg-panel" style={{ height: gridHeight }}>
              {hours.map((hour, index) => (
                <span
                  key={hour}
                  aria-hidden="true"
                  className="absolute inset-x-0 border-t border-line/70"
                  style={{ top: index * CALENDAR_HOUR_HEIGHT }}
                />
              ))}
              {onSelectSlot
                ? slots.map((start) => (
                    <button
                      key={start}
                      type="button"
                      onClick={() =>
                        onSelectSlot({
                          date: anchorDate,
                          time: timeLabel(start),
                          workerId: column.id === 'all' ? undefined : column.id,
                        })
                      }
                      aria-label={
                        column.id === 'all'
                          ? `Crear reserva el ${formatDateLabel(anchorDate)} a las ${timeLabel(start)}`
                          : `Crear reserva el ${formatDateLabel(anchorDate)} a las ${timeLabel(start)} con ${column.label}`
                      }
                      className="absolute inset-x-0 z-0 transition hover:bg-surface focus-visible:bg-brand-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
                      style={slotBlockStyle(start, startHour, endHour)}
                    />
                  ))
                : null}
              {column.bookings.map((booking) => (
                <button
                  type="button"
                  key={booking.id}
                  onClick={() => onSelectBooking(booking)}
                  className="absolute inset-x-1 z-10 overflow-hidden rounded-md border-l-4 bg-surface p-1.5 text-left text-xs transition hover:bg-brand-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
                  style={{
                    ...bookingBlockStyle(booking, startHour, endHour, timezone),
                    borderLeftColor: column.color,
                  }}
                >
                  <span className="block font-semibold text-ink">
                    {formatTime(booking.start_at, timezone)} {booking.customer_name}
                  </span>
                  <span className="block truncate text-muted">{booking.service_name}</span>
                  <span className="sr-only">Ver reserva</span>
                </button>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
