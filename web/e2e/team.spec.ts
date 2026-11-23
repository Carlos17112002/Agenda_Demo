import { expect, test } from '@playwright/test';

import { WEEKDAYS } from '../src/lib/format';
import type { Seed } from './support/seed';
import {
  BOOKING_OFFSET_DAYS,
  seedCompany,
  uniqueSuffix,
  weekdayIndex,
} from './support/seed';
import { installSession, readSharedSession } from './support/session';

const session = readSharedSession();
let seed: Seed;

test.beforeAll(async () => {
  seed = await seedCompany(session, uniqueSuffix());
});

test('crea servicio y trabajador, agrega horario y ofrece cupos', async ({ page }) => {
  const suffix = uniqueSuffix();
  const serviceName = `Servicio UI ${suffix}`;
  const workerName = `Trabajador ${suffix}`;

  await installSession(page, session);

  await page.goto('/servicios');
  await expect(page.getByRole('heading', { name: 'Servicios' })).toBeVisible();
  await page.getByRole('button', { name: 'Nuevo servicio' }).click();
  let dialog = page.getByRole('dialog');
  await dialog.getByLabel('Nombre').fill(serviceName);
  await dialog.getByLabel('Duración (minutos)').fill('45');
  await dialog.getByLabel('Precio').fill('18000');
  await dialog.getByRole('checkbox', { name: seed.branch.name }).check();
  await dialog.getByRole('button', { name: 'Guardar servicio' }).click();
  await expect(dialog).toBeHidden();

  await page.getByLabel('Buscar').fill(serviceName);
  await expect(page.getByRole('row', { name: new RegExp(serviceName) })).toBeVisible();

  await page.goto('/equipo');
  await expect(page.getByRole('heading', { name: 'Equipo' })).toBeVisible();
  await page.getByRole('button', { name: 'Nuevo trabajador' }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('Nombre').fill('Trabajador');
  await dialog.getByLabel('Apellido').fill(suffix);
  await dialog.getByLabel('Cargo').fill('E2E');
  await dialog.getByRole('checkbox', { name: seed.branch.name }).check();
  await dialog.getByRole('button', { name: 'Guardar trabajador' }).click();
  await expect(dialog).toBeHidden();

  await page.getByLabel('Buscar').fill(`Trabajador ${suffix}`);
  const workerRow = page.getByRole('row', { name: new RegExp(`Trabajador ${suffix}`) });
  await expect(workerRow).toBeVisible();
  await workerRow.getByRole('button', { name: 'Horario' }).click();

  await expect(page.getByRole('button', { name: 'Agregar horario' })).toBeVisible();
  await page.getByRole('button', { name: 'Agregar horario' }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('Sucursal').selectOption({ label: seed.branch.name });
  await dialog.getByLabel('Día').selectOption({ label: WEEKDAYS[weekdayIndex(seed.date)] });
  await dialog.getByLabel('Inicio').fill('08:00');
  await dialog.getByLabel('Término').fill('20:00');
  await dialog.getByRole('button', { name: 'Guardar horario' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText('08:00').first()).toBeVisible();

  await page.goto('/agenda');
  await expect(page.getByRole('heading', { name: 'Agenda' })).toBeVisible();
  await page.getByLabel('Sucursal').selectOption({ label: seed.branch.name });
  for (let index = 0; index < BOOKING_OFFSET_DAYS; index += 1) {
    await page.getByRole('button', { name: 'Siguiente' }).click();
  }

  await page.getByRole('button', { name: 'Nueva reserva' }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('Sucursal').selectOption({ label: seed.branch.name });
  await dialog.getByLabel('Día').fill(seed.date);
  await dialog.getByLabel('Servicio').selectOption({ label: `${serviceName} · 45 min` });
  await dialog.getByLabel('Trabajador').selectOption({ label: workerName });

  await expect(dialog.getByRole('button', { name: /^\d{2}:\d{2}$/ }).first()).toBeVisible();
});
