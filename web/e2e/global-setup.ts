import { request } from '@playwright/test';

import { openSession } from './support/api';
import { e2eEnv } from './support/env';
import { writeSharedSession } from './support/session';

export default async function globalSetup() {
  const health = await request.newContext({ baseURL: e2eEnv.apiBaseUrl });
  try {
    const response = await health.get('/api/v1/plans/');
    if (!response.ok()) {
      throw new Error(`La API respondió ${response.status()} en ${e2eEnv.apiBaseUrl}.`);
    }
  } catch (error) {
    throw new Error(
      `No se pudo contactar la API en ${e2eEnv.apiBaseUrl}. ` +
        `Inicia Django con "python manage.py runserver" desde backend/. Detalle: ${String(error)}`,
    );
  } finally {
    await health.dispose();
  }
  writeSharedSession(await openSession(e2eEnv.companyName));
}
