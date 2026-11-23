type ZoneParts = {
  year: string;
  month: string;
  day: string;
  hour: string;
  minute: string;
  second: string;
};

function partsInZone(date: Date, timeZone: string): ZoneParts {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
  const values: Record<string, string> = {};
  formatter.formatToParts(date).forEach((part) => {
    if (part.type !== 'literal') values[part.type] = part.value;
  });
  return {
    year: values.year,
    month: values.month,
    day: values.day,
    hour: values.hour,
    minute: values.minute,
    second: values.second,
  };
}

function zoneOffsetMs(date: Date, timeZone: string): number {
  const parts = partsInZone(date, timeZone);
  const asUtc = Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour),
    Number(parts.minute),
    Number(parts.second),
  );
  return asUtc - date.getTime();
}

export function todayInZone(timeZone: string, now = new Date()): string {
  const parts = partsInZone(now, timeZone);
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function formatDateISO(value: string, timeZone: string): string {
  const parts = partsInZone(new Date(value), timeZone);
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function shiftDate(dateISO: string, days: number): string {
  const [year, month, day] = dateISO.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day + days));
  return date.toISOString().slice(0, 10);
}

export function weekRange(dateISO: string): { date_from: string; date_to: string } {
  const [year, month, day] = dateISO.split('-').map(Number);
  const weekday = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  const offset = weekday === 0 ? -6 : 1 - weekday;
  const monday = shiftDate(dateISO, offset);
  return { date_from: monday, date_to: shiftDate(monday, 6) };
}

export function formatTime(value: string, timeZone: string): string {
  return new Intl.DateTimeFormat('es-CL', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(new Date(value));
}

export function formatDateLabel(dateISO: string): string {
  const [year, month, day] = dateISO.split('-').map(Number);
  return new Intl.DateTimeFormat('es-CL', {
    timeZone: 'UTC',
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  }).format(new Date(Date.UTC(year, month - 1, day, 12)));
}

export function formatDateTime(value: string, timeZone: string): string {
  const dateISO = formatDateISO(value, timeZone);
  return `${formatDateLabel(dateISO)} · ${formatTime(value, timeZone)}`;
}

export function dateTimeLocalToISO(value: string, timeZone: string): string {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) {
    throw new Error('Fecha y hora inválidas.');
  }
  const [datePart, timePart] = value.split('T');
  const [year, month, day] = datePart.split('-').map(Number);
  const [hour, minute] = timePart.split(':').map(Number);
  const naiveUtc = Date.UTC(year, month - 1, day, hour, minute, 0);
  const firstOffset = zoneOffsetMs(new Date(naiveUtc), timeZone);
  let result = new Date(naiveUtc - firstOffset);
  const secondOffset = zoneOffsetMs(result, timeZone);
  if (secondOffset !== firstOffset) result = new Date(naiveUtc - secondOffset);
  return result.toISOString();
}

export function isoToDateTimeLocal(value: string, timeZone: string): string {
  const parts = partsInZone(new Date(value), timeZone);
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}
