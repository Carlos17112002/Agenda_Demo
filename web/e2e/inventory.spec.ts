import { expect, test } from '@playwright/test';

import { apiCall, apiUpload } from './support/api';
import type { Seed } from './support/seed';
import { seedCompany, uniqueSuffix } from './support/seed';
import { installSession, readSharedSession } from './support/session';

const session = readSharedSession();
let seed: Seed;
let assetName: string;
let serialNumber: string;
let document: { name: string; original_name: string };

test.beforeAll(async () => {
  const suffix = uniqueSuffix();
  seed = await seedCompany(session, suffix);
  assetName = `Máquina ${suffix}`;
  serialNumber = `SER-${suffix}`;
  const auth = { token: session.access, contextId: session.contextId };

  const asset = await apiCall<{ id: string }>('/api/v1/inventory/products/', {
    ...auth,
    method: 'POST',
    body: {
      kind: 'asset',
      name: assetName,
      status: 'available',
      branch: seed.branch.id,
      serial_number: serialNumber,
      active: true,
    },
  });

  const form = new FormData();
  form.append('name', `Ficha ${suffix}`);
  form.append('product', asset.id);
  form.append(
    'file',
    new Blob([`Contenido E2E ${suffix}`], { type: 'text/plain' }),
    `ficha-${suffix}.txt`,
  );
  document = await apiUpload<{ name: string; original_name: string }>(
    '/api/v1/inventory/documents/',
    form,
    auth,
  );
});

test('consulta objetos, busca el archivo y lo descarga', async ({ page }) => {
  await installSession(page, session);
  await page.goto('/inventario');
  await expect(page.getByRole('heading', { name: 'Inventario' })).toBeVisible();

  const objects = page.getByRole('tabpanel', { name: 'Objetos' });
  await objects.getByLabel('Buscar objeto').fill(assetName);
  const assetRow = objects.getByRole('row', { name: new RegExp(assetName) });
  await expect(assetRow).toBeVisible();
  await expect(assetRow).toContainText(serialNumber);

  await page.getByRole('tab', { name: 'Archivos' }).click();
  const files = page.getByRole('tabpanel', { name: 'Archivos' });
  await files.getByLabel('Buscar archivo').fill(document.name);
  await expect(
    files.getByRole('row', { name: new RegExp(document.original_name) }),
  ).toBeVisible();

  const downloadStarted = page.waitForEvent('download');
  await files.getByRole('button', { name: `Descargar ${document.name}` }).click();
  const download = await downloadStarted;
  expect(download.suggestedFilename()).toBe(document.original_name);
});
