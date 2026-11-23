import { expect, test, type Page } from '@playwright/test';

import { e2eEnv } from './support/env';

test.describe.configure({ mode: 'serial' });

async function signIn(page: Page) {
  await page.goto('/login');
  await page.getByLabel('Correo', { exact: true }).fill(e2eEnv.email);
  await page.getByLabel('Contraseña', { exact: true }).fill(e2eEnv.password);
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page.getByRole('heading', { name: /Elige una empresa|Agenda/ })).toBeVisible();

  if (await page.getByRole('heading', { name: 'Elige una empresa' }).isVisible()) {
    await page.getByRole('button', { name: new RegExp(e2eEnv.companyName) }).click();
  }

  await expect(page.getByRole('heading', { name: 'Agenda' })).toBeVisible();
}

test('inicia sesión y entra a la agenda de la empresa', async ({ page }) => {
  await signIn(page);
  await expect(page.getByRole('navigation', { name: 'Secciones' }).first()).toBeVisible();
});

test('rechaza credenciales inválidas', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Correo', { exact: true }).fill(e2eEnv.email);
  await page.getByLabel('Contraseña', { exact: true }).fill(`${e2eEnv.password}-incorrecta`);
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test('cierra la sesión y limpia el almacenamiento', async ({ page }) => {
  await signIn(page);
  await page.getByRole('button', { name: 'Salir' }).click();

  await expect(page.getByRole('heading', { name: 'Panel del operador' })).toBeVisible();
  const keys = await page.evaluate(() => Object.keys(localStorage));
  expect(keys).toEqual([]);
});
