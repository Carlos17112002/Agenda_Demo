import { expect, test } from '@playwright/test';

import { installSession, readSharedSession } from './support/session';

const session = readSharedSession();

test('restaura la sesión al recargar y solo persiste tokens y contexto', async ({ page }) => {
  await installSession(page, session);
  await page.goto('/agenda');
  await expect(page.getByRole('heading', { name: 'Agenda' })).toBeVisible();

  await page.reload();
  await expect(page.getByRole('heading', { name: 'Agenda' })).toBeVisible();

  const keys = await page.evaluate(() => Object.keys(localStorage).sort());
  expect(keys).toEqual(['agenda.web.refresh', 'agenda.web.session']);
});
