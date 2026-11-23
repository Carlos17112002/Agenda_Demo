import { expect, test } from '@playwright/test';

import { apiCall } from './support/api';
import { uniqueSuffix } from './support/seed';
import { installSession, readSharedSession } from './support/session';

type Branding = {
  display_name: string;
  slug: string;
  primary_color: string;
  secondary_color: string;
  theme_mode: 'light' | 'dark';
  booking_url: string;
};

const session = readSharedSession();
let original: Branding;

test.beforeAll(async () => {
  original = await apiCall<Branding>('/api/v1/company/branding/', {
    token: session.access,
    contextId: session.contextId,
  });
});

test.afterAll(async () => {
  await apiCall('/api/v1/company/branding/', {
    method: 'PATCH',
    token: session.access,
    contextId: session.contextId,
    body: {
      display_name: original.display_name,
      slug: original.slug,
      primary_color: original.primary_color,
      secondary_color: original.secondary_color,
      theme_mode: original.theme_mode,
    },
  });
});

test('actualiza nombre y tema y conserva el enlace público', async ({ page }) => {
  const updatedName = `Aurora E2E ${uniqueSuffix()}`;

  await installSession(page, session);
  await page.goto('/marca');
  await expect(page.getByRole('heading', { name: 'Marca' })).toBeVisible();

  await page.getByLabel('Nombre visible').fill(updatedName);
  await page.getByLabel('Tema').selectOption('dark');
  await page.getByRole('button', { name: 'Guardar cambios' }).click();

  await expect(
    page.getByRole('status').filter({ hasText: 'Marca actualizada.' }),
  ).toBeVisible();
  await expect(page.locator('aside').first().getByText(updatedName)).toBeVisible();
  await expect(page.getByText('Enlace público actual')).toBeVisible();
  await expect(page.getByText(original.booking_url)).toBeVisible();
});
