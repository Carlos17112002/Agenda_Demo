import { expect, test, type Page } from '@playwright/test';

import { formatDateLabel, formatTime } from '../src/lib/dates';
import { apiCall } from './support/api';
import type { Seed } from './support/seed';
import { BOOKING_OFFSET_DAYS, seedCompany, uniqueSuffix } from './support/seed';
import { installSession, readSharedSession } from './support/session';

const session = readSharedSession();
let seed: Seed;

test.beforeAll(async () => {
  seed = await seedCompany(session, uniqueSuffix());
});

async function openSeededDay(page: Page) {
  await installSession(page, session);
  await page.goto('/agenda');
  await expect(page.getByRole('heading', { name: 'Agenda' })).toBeVisible();
  await page.getByLabel('Sucursal').selectOption({ label: seed.branch.name });
  for (let index = 0; index < BOOKING_OFFSET_DAYS; index += 1) {
    await page.getByRole('button', { name: 'Siguiente' }).click();
  }
}

test('crea, reprograma y cancela una reserva con un cupo real', async ({ page }) => {
  await openSeededDay(page);

  await page.getByRole('button', { name: 'Nueva reserva' }).click();
  const createDialog = page.getByRole('dialog');
  await createDialog.getByLabel('Sucursal').selectOption({ label: seed.branch.name });
  await createDialog.getByLabel('Día').fill(seed.date);
  await createDialog
    .getByLabel('Servicio')
    .selectOption({ label: `${seed.service.name} · 30 min` });
  await createDialog
    .getByLabel('Trabajador')
    .selectOption({ label: seed.worker.display_name });

  const slots = createDialog.getByRole('button', { name: /^\d{2}:\d{2}$/ });
  await expect(slots.first()).toBeVisible();
  await slots.first().click();

  await createDialog.getByLabel('Buscar cliente').fill(seed.customer.display_name);
  await createDialog.getByLabel('Cliente', { exact: true }).selectOption(seed.customer.id);
  await createDialog.getByLabel('Notas').fill('Reserva creada desde E2E');
  await createDialog.getByRole('button', { name: 'Crear reserva' }).click();

  await expect(createDialog).toBeHidden();
  const bookingBlock = page.getByRole('button', {
    name: new RegExp(seed.customer.display_name),
  });
  await expect(bookingBlock).toHaveCount(1);

  await bookingBlock.click();
  const detail = page.getByRole('dialog');
  const startBefore = await detail.locator('dd').first().textContent();

  await detail.getByRole('button', { name: 'Reprogramar' }).click();
  const rescheduleSlots = detail.getByRole('button', { name: /^\d{2}:\d{2}$/ });
  await expect(rescheduleSlots.nth(1)).toBeVisible();
  await rescheduleSlots.nth(1).click();
  await detail.getByRole('button', { name: 'Reprogramar reserva' }).click();
  await expect(detail.locator('dd').first()).not.toHaveText(startBefore ?? '');

  await detail.getByRole('button', { name: 'Cancelar reserva' }).click();
  await detail.getByLabel('Motivo de cancelación').fill('Cancelada desde E2E');
  await detail.getByRole('button', { name: 'Confirmar cancelación' }).click();
  await expect(detail.getByText('Cancelada')).toBeVisible();

  await detail.getByRole('button', { name: 'Cerrar' }).last().click();
  await expect(
    page.getByRole('button', { name: new RegExp(seed.customer.display_name) }),
  ).toBeVisible();
});

test('abre el alta desde un hueco con día, hora y cupo preseleccionados', async ({ page }) => {
  const availability = await apiCall<{ slots: { start_at: string }[] }>(
    `/api/v1/bookings/availability/?branch=${seed.branch.id}&service=${seed.service.id}` +
      `&worker=${seed.worker.id}&date=${seed.date}`,
    { token: session.access, contextId: session.contextId },
  );
  const times = availability.slots.map((slot) => formatTime(slot.start_at, seed.branch.timezone));
  const slotTime = times.find((time) => time === '14:00') ?? times[0];

  await openSeededDay(page);
  await page.getByLabel('Trabajador').selectOption({ label: seed.worker.display_name });
  await page.getByRole('button', { name: 'Semana' }).click();
  await expect(page.getByRole('heading', { name: formatDateLabel(seed.date) })).toBeVisible();

  await page
    .getByRole('button', {
      name: `Crear reserva el ${formatDateLabel(seed.date)} a las ${slotTime}`,
    })
    .click();

  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/Horario solicitado desde la agenda/)).toBeVisible();
  await expect(dialog.getByLabel('Día')).toHaveValue(seed.date);

  await dialog
    .getByLabel('Servicio')
    .selectOption({ label: `${seed.service.name} · 30 min` });
  await dialog
    .getByLabel('Trabajador')
    .selectOption({ label: seed.worker.display_name });

  await expect(dialog.getByRole('button', { name: new RegExp(`^${slotTime}$`) })).toBeVisible();
  await dialog.getByLabel('Buscar cliente').fill(seed.customer.display_name);
  await dialog.getByLabel('Cliente', { exact: true }).selectOption(seed.customer.id);
  await dialog.getByRole('button', { name: 'Crear reserva' }).click();

  await expect(dialog).toBeHidden();
  await expect(
    page.getByRole('button', {
      name: new RegExp(`^${slotTime} ${seed.customer.display_name}.*Ver reserva`),
    }),
  ).toBeVisible();
});
