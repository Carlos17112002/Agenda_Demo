import { expect, test } from '@playwright/test';

import { seedCompany, uniqueSuffix } from './support/seed';
import { installSession, readSharedSession } from './support/session';

const session = readSharedSession();

test('crea un usuario con local, fuerza el cambio de clave y abre la agenda en ese local', async ({
  page,
}) => {
  const seed = await seedCompany(session, uniqueSuffix());
  const email = `nueva-${uniqueSuffix()}@example.com`;

  await installSession(page, session);
  await page.goto('/usuarios');
  await expect(page.getByRole('heading', { name: 'Usuarios' })).toBeVisible();

  await page.getByRole('button', { name: 'Nuevo usuario' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Correo').fill(email);
  await dialog.getByLabel('Nombre').fill('Nueva');
  await dialog.getByLabel('Apellido').fill('Persona');
  await dialog.getByLabel('Rol').selectOption('reception');
  await dialog.getByLabel('Local predeterminado').selectOption({ label: seed.branch.name });
  await dialog.getByRole('button', { name: 'Crear usuario' }).click();

  const credentials = page.getByRole('dialog', { name: 'Credenciales de acceso' });
  await expect(credentials).toBeVisible();
  const password = await credentials.getByTestId('temporary-password').innerText();
  await credentials.getByRole('button', { name: 'Entendido' }).click();

  await page.getByRole('button', { name: 'Salir' }).click();
  await expect(page.getByRole('heading', { name: 'Panel del operador' })).toBeVisible();
  await page.getByLabel('Correo').fill(email);
  await page.getByLabel('Contraseña').fill(password);
  await page.getByRole('button', { name: 'Entrar' }).click();

  await page.getByLabel('Nueva contraseña').fill('Clave-Nueva-2026!');
  await page.getByLabel('Repetir contraseña').fill('Clave-Nueva-2026!');
  await page.getByLabel('Contraseña actual').fill(password);
  await page.getByRole('button', { name: 'Actualizar contraseña' }).click();

  await expect(page.getByRole('heading', { name: 'Agenda' })).toBeVisible();
  await expect(page.getByLabel('Sucursal')).toHaveValue(seed.branch.id);
});
