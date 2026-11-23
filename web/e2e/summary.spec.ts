import { expect, test } from '@playwright/test';

import { formatMoney } from '../src/lib/format';
import { apiCall } from './support/api';
import type { Seed } from './support/seed';
import { seedCompany, uniqueSuffix } from './support/seed';
import { installSession, readSharedSession } from './support/session';

type SalesSummary = { totals: { total: string } };
type CashSummary = {
  totals: { sessions: number; expected: string; closing: string; difference: string; expenses: string };
};

const session = readSharedSession();
let seed: Seed;

test.beforeAll(async () => {
  seed = await seedCompany(session, uniqueSuffix());
});

test('compara los totales con la API y filtra por sucursal', async ({ page }) => {
  await installSession(page, session);
  await page.goto('/resumen');
  await expect(page.getByRole('heading', { name: 'Resumen' })).toBeVisible();

  const from = await page.getByLabel('Desde').inputValue();
  const to = await page.getByLabel('Hasta').inputValue();
  expect(from).not.toBe('');
  expect(to).not.toBe('');

  const auth = { token: session.access, contextId: session.contextId };
  const sales = await apiCall<SalesSummary>(
    `/api/v1/reports/sales-summary/?date_from=${from}&date_to=${to}`,
    auth,
  );
  await expect(page.getByText('Total vendido').locator('..')).toContainText(
    formatMoney(sales.totals.total),
  );

  const cash = await apiCall<CashSummary>(
    `/api/v1/reports/cash-summary/?date_from=${from}&date_to=${to}`,
    auth,
  );
  const cashSection = page.getByRole('region', { name: 'Caja' });
  await expect(
    cashSection.locator('p', { hasText: /^Sesiones$/ }).locator('..'),
  ).toContainText(String(cash.totals.sessions));
  await expect(
    cashSection.locator('p', { hasText: /^Esperado$/ }).locator('..'),
  ).toContainText(formatMoney(cash.totals.expected));

  const filtered = page.waitForRequest(
    (request) =>
      request.url().includes('/reports/sales-summary/') &&
      request.url().includes(`branch=${seed.branch.id}`),
  );
  await page.getByLabel('Sucursal').selectOption({ label: seed.branch.name });
  await filtered;

  const branchSales = await apiCall<SalesSummary>(
    `/api/v1/reports/sales-summary/?date_from=${from}&date_to=${to}&branch=${seed.branch.id}`,
    auth,
  );
  await expect(page.getByText('Total vendido').locator('..')).toContainText(
    formatMoney(branchSales.totals.total),
  );
});
