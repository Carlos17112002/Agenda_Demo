import { expect, test } from '@playwright/test';

import type { Seed } from './support/seed';
import { seedCompany, uniqueSuffix } from './support/seed';
import { installSession, readSharedSession } from './support/session';

const session = readSharedSession();
let seed: Seed;

test.beforeAll(async () => {
  seed = await seedCompany(session, uniqueSuffix(), { withBooking: true });
});

test('busca un cliente y abre su historial de reservas', async ({ page }) => {
  await installSession(page, session);
  await page.goto('/clientes');
  await expect(page.getByRole('heading', { name: 'Clientes' })).toBeVisible();

  await page.getByLabel('Buscar').fill(seed.customer.display_name);
  const row = page.getByRole('row', { name: new RegExp(seed.customer.display_name) });
  await expect(row).toBeVisible();

  await row.getByRole('button', { name: 'Historial' }).click();
  const history = page.getByRole('dialog');
  await expect(
    history.getByRole('heading', { name: `Historial de ${seed.customer.display_name}` }),
  ).toBeVisible();
  await expect(history.getByText(seed.service.name)).toBeVisible();
  await expect(history.getByText('Agendada')).toBeVisible();
});

test('crea un cliente desde el panel y lo encuentra por búsqueda', async ({ page }) => {
  const suffix = uniqueSuffix();
  await installSession(page, session);
  await page.goto('/clientes');
  await expect(page.getByRole('heading', { name: 'Clientes' })).toBeVisible();

  await page.getByRole('button', { name: 'Nuevo cliente' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Nombre').fill('Cliente');
  await dialog.getByLabel('Apellido').fill(suffix);
  await dialog.getByLabel('Correo').fill(`e2e-cliente-${suffix}@example.com`);
  await dialog.getByLabel('Teléfono').fill('+56922223333');
  await dialog.getByRole('button', { name: 'Guardar cliente' }).click();
  await expect(dialog).toBeHidden();

  await page.getByLabel('Buscar').fill(`Cliente ${suffix}`);
  await expect(page.getByRole('row', { name: new RegExp(`Cliente ${suffix}`) })).toBeVisible();
});
