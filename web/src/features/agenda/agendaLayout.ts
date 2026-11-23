import type { Booking } from '../../api/agenda';
import type { Worker, WorkingHours } from '../../api/team';
import { formatDateISO, formatTime, shiftDate } from '../../lib/dates';

const DEFAULT_START_HOUR = 8;
const DEFAULT_END_HOUR = 20;

export const CALENDAR_HOUR_HEIGHT = 64;

export type CalendarSlot = { date: string; time: string; workerId?: string };

export function weekdayIndex(dateISO: string): number {
  const [year, month, day] = dateISO.split('-').map(Number);
  return (new Date(Date.UTC(year, month - 1, day)).getUTCDay() + 6) % 7;
}

function minutesOfTime(value: string): number {
  const [hour, minute] = value.split(':').map(Number);
  return (hour || 0) * 60 + (minute || 0);
}

function localMinutes(value: string, timeZone: string): number {
  const [hour, minute] = formatTime(value, timeZone).split(':').map(Number);
  return hour * 60 + minute;
}

export function hourBounds(
  bookings: Booking[],
  timeZone: string,
  shifts: WorkingHours[] = [],
  weekdays?: number[],
): { startHour: number; endHour: number } {
  const visible = weekdays && weekdays.length > 0 ? new Set(weekdays) : null;
  let shiftStart: number | null = null;
  let shiftEnd: number | null = null;
  shifts.forEach((shift) => {
    if (visible && !visible.has(shift.weekday)) return;
    const start = minutesOfTime(shift.start_time);
    const rawEnd = minutesOfTime(shift.end_time);
    const end = rawEnd === 0 ? 24 * 60 : rawEnd;
    if (end <= start) return;
    shiftStart = shiftStart === null ? start : Math.min(shiftStart, start);
    shiftEnd = shiftEnd === null ? end : Math.max(shiftEnd, end);
  });

  let startHour = shiftStart === null ? DEFAULT_START_HOUR : Math.floor(shiftStart / 60);
  let endHour = shiftEnd === null ? DEFAULT_END_HOUR : Math.ceil(shiftEnd / 60);
  bookings.forEach((booking) => {
    const start = localMinutes(booking.start_at, timeZone);
    const end = start + booking.duration_minutes;
    startHour = Math.min(startHour, Math.floor(start / 60));
    if (end > start) endHour = Math.max(endHour, Math.ceil(end / 60));
  });
  return {
    startHour: Math.max(0, startHour),
    endHour: Math.min(24, Math.max(startHour + 2, endHour)),
  };
}

export function slotStepMinutes(startHour: number, endHour: number): number {
  return endHour - startHour > 16 ? 60 : 30;
}

export function slotStarts(startHour: number, endHour: number): number[] {
  const step = slotStepMinutes(startHour, endHour);
  const total = (endHour - startHour) * 60;
  return Array.from({ length: Math.floor(total / step) }, (_, index) => startHour * 60 + index * step);
}

export function timeLabel(minutes: number): string {
  const hour = Math.floor(minutes / 60);
  const minute = minutes % 60;
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
}

export function slotBlockStyle(
  startMinutes: number,
  startHour: number,
  endHour: number,
): { top: string; height: string } {
  const total = (endHour - startHour) * 60;
  const step = slotStepMinutes(startHour, endHour);
  return {
    top: `${((startMinutes - startHour * 60) / total) * 100}%`,
    height: `${(step / total) * 100}%`,
  };
}

export function bookingBlockStyle(
  booking: Booking,
  startHour: number,
  endHour: number,
  timeZone: string,
): { top: string; height: string } {
  const total = (endHour - startHour) * 60;
  const start = localMinutes(booking.start_at, timeZone) - startHour * 60;
  const top = Math.max(0, Math.min(100, (start / total) * 100));
  const height = Math.max(1.5, Math.min(100 - top, (booking.duration_minutes / total) * 100));
  return { top: `${top}%`, height: `${height}%` };
}

export function bookingsForWorker(bookings: Booking[], workerId: string): Booking[] {
  return bookings
    .filter((booking) => booking.worker === workerId)
    .sort((first, second) => first.start_at.localeCompare(second.start_at));
}

export function overlapLanes(
  bookings: Booking[],
  timeZone: string,
): { lanes: number; laneOf: Map<string, number> } {
  const ordered = bookings
    .map((booking) => {
      const start = localMinutes(booking.start_at, timeZone);
      return { booking, start, end: start + booking.duration_minutes };
    })
    .sort((first, second) => first.start - second.start || first.end - second.end);
  const laneEnds: number[] = [];
  const laneOf = new Map<string, number>();
  ordered.forEach((item) => {
    let lane = laneEnds.findIndex((end) => end <= item.start);
    if (lane === -1) {
      lane = laneEnds.length;
      laneEnds.push(item.end);
    } else {
      laneEnds[lane] = item.end;
    }
    laneOf.set(item.booking.id, lane);
  });
  return { lanes: Math.max(1, laneEnds.length), laneOf };
}

export function groupWeek(
  bookings: Booking[],
  dateFrom: string,
  timeZone: string,
): { date: string; bookings: Booking[] }[] {
  return Array.from({ length: 7 }, (_, index) => {
    const date = shiftDate(dateFrom, index);
    return {
      date,
      bookings: bookings
        .filter((booking) => formatDateISO(booking.start_at, timeZone) === date)
        .sort((first, second) => first.start_at.localeCompare(second.start_at)),
    };
  });
}

export function workersForColumns(workers: Worker[], selectedWorker: string): Worker[] {
  return selectedWorker ? workers.filter((worker) => worker.id === selectedWorker) : workers;
}
