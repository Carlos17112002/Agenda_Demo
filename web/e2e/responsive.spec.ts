import { expect, test } from '@playwright/test';

import { installSession, readSharedSession } from './support/session';

const session = readSharedSession();

test.use({ viewport: { width: 768, height: 1024 } });

test('las pantallas principales no desbordan horizontalmente a 768 px', async ({ page }) => {
  await installSession(page, session);

  for (const path of ['/agenda', '/clientes', '/servicios', '/equipo', '/inventario', '/resumen', '/marca']) {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow, `${path} desborda ${overflow} px`).toBeLessThanOrEqual(0);
  }
});
