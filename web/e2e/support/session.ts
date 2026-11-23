import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

import type { Page } from '@playwright/test';

import type { E2ESession } from './api';

const authDirectory = new URL('../.auth/', import.meta.url);
const sessionFile = new URL('session.json', authDirectory);

export function writeSharedSession(session: E2ESession): void {
  mkdirSync(authDirectory, { recursive: true });
  writeFileSync(sessionFile, JSON.stringify(session, null, 2), 'utf8');
}

export function readSharedSession(): E2ESession {
  return JSON.parse(readFileSync(sessionFile, 'utf8')) as E2ESession;
}

export async function installSession(
  page: Page,
  session: E2ESession = readSharedSession(),
): Promise<void> {
  await page.addInitScript(
    ({ refresh, stored }) => {
      localStorage.setItem('agenda.web.refresh', refresh);
      localStorage.setItem('agenda.web.session', JSON.stringify(stored));
    },
    {
      refresh: session.refresh,
      stored: {
        companyId: session.companyId,
        contextId: session.contextId,
        companyName: session.companyName,
      },
    },
  );

  await page.route('**/api/v1/auth/token/refresh/', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access: session.access, refresh: session.refresh }),
    }),
  );
}
