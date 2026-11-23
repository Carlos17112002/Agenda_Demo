import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { installSession, readSharedSession } from './support/session';

const session = readSharedSession();

const pages = [
  { path: '/agenda', title: 'Agenda' },
  { path: '/clientes', title: 'Clientes' },
  { path: '/servicios', title: 'Servicios' },
  { path: '/equipo', title: 'Equipo' },
  { path: '/inventario', title: 'Inventario' },
  { path: '/resumen', title: 'Resumen' },
  { path: '/marca', title: 'Marca' },
] as const;

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

function summarize(violations: { id: string }[]): string {
  return violations.map((violation) => violation.id).join(', ');
}

async function audit(page: Parameters<typeof installSession>[0], path: string, title: string) {
  await page.goto(path);
  await expect(page.getByRole('heading', { name: title })).toBeVisible();
  await page.waitForLoadState('networkidle');
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  expect(results.violations, `${path}: ${summarize(results.violations)}`).toEqual([]);
}

test('las pantallas principales cumplen WCAG AA en ambos temas', async ({ page }) => {
  test.setTimeout(240_000);
  await installSession(page, session);

  for (const item of pages) {
    await audit(page, item.path, item.title);
  }

  await page.goto('/agenda');
  const toggle = page.getByRole('button', { name: /Tema (claro|oscuro)/ });
  const current = (await toggle.textContent())?.trim();
  await toggle.click();
  await expect(
    page.getByRole('button', { name: current === 'Tema oscuro' ? 'Tema claro' : 'Tema oscuro' }),
  ).toBeVisible();

  for (const item of pages) {
    await audit(page, item.path, item.title);
  }
});

test('el diálogo de nueva reserva cumple AA', async ({ page }) => {
  await installSession(page, session);
  await page.goto('/agenda');
  await expect(page.getByRole('heading', { name: 'Agenda' })).toBeVisible();
  await page.getByRole('button', { name: 'Nueva reserva' }).click();

  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const results = await new AxeBuilder({ page })
    .include('[role="dialog"]')
    .withTags(TAGS)
    .analyze();
  expect(results.violations, summarize(results.violations)).toEqual([]);

  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
});
