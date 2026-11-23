import { expect, test } from '@playwright/test';

import { listCompanies } from './support/api';
import type { Seed } from './support/seed';
import { seedCompany, uniqueSuffix } from './support/seed';
import { installSession, readSharedSession } from './support/session';

const session = readSharedSession();
let seed: Seed;

test.beforeAll(async () => {
  seed = await seedCompany(session, uniqueSuffix());
});

test('cambiar de empresa usa otro contexto y no muestra datos previos', async ({ page }) => {
  const companies = await listCompanies(session.access);
  test.skip(
    companies.length < 2,
    'La cuenta E2E necesita al menos dos empresas para probar el aislamiento.',
  );
  const other = companies.find((item) => item.id !== session.companyId);
  if (!other) throw new Error('No se encontró una segunda empresa.');

  const customerHeaders: string[] = [];
  page.on('request', (request) => {
    if (request.url().includes('/api/v1/customers/') && request.method() === 'GET') {
      customerHeaders.push(request.headers()['x-tenant-context'] ?? '');
    }
  });

  await installSession(page, session);
  await page.goto('/clientes');
  await page.getByLabel('Buscar').fill(seed.customer.display_name);
  await expect(
    page.getByRole('row', { name: new RegExp(seed.customer.display_name) }),
  ).toBeVisible();

  await expect.poll(() => customerHeaders.length).toBeGreaterThan(0);
  expect(customerHeaders).toContain(session.contextId);

  await page.getByLabel('Empresa').selectOption({ label: other.display_name || other.name });
  await expect(page).toHaveURL(/\/agenda$/);

  await expect.poll(async () => {
    const raw = await page.evaluate(() => localStorage.getItem('agenda.web.session'));
    return raw ? (JSON.parse(raw) as { companyId: string }).companyId : '';
  }).toBe(other.id);

  customerHeaders.length = 0;
  await page.getByRole('link', { name: 'Clientes' }).click();
  await page.getByLabel('Buscar').fill(seed.customer.display_name);
  await expect(
    page.getByRole('row', { name: new RegExp(seed.customer.display_name) }),
  ).toHaveCount(0);

  await expect.poll(() => customerHeaders.length).toBeGreaterThan(0);
  expect(customerHeaders.every((contextId) => contextId !== session.contextId)).toBe(true);
});
