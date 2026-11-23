import { readFileSync } from 'node:fs';

function readDotEnv(): Record<string, string> {
  try {
    const raw = readFileSync(new URL('../../.env.e2e', import.meta.url), 'utf8');
    const entries = raw
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0 && !line.startsWith('#') && line.includes('='))
      .map((line) => {
        const index = line.indexOf('=');
        return [line.slice(0, index).trim(), line.slice(index + 1).trim()] as const;
      });
    return Object.fromEntries(entries);
  } catch {
    return {};
  }
}

const file = readDotEnv();

function read(key: string, fallback = ''): string {
  return process.env[key] ?? file[key] ?? fallback;
}

export const e2eEnv = {
  webBaseUrl: read('E2E_WEB_URL', 'http://127.0.0.1:5173'),
  apiBaseUrl: read('E2E_API_URL', 'http://127.0.0.1:8000'),
  email: read('E2E_EMAIL', 'superadmin@agenda.app'),
  password: read('E2E_PASSWORD'),
  companyName: read('E2E_COMPANY', 'Estudio Aurora'),
  otherCompanyName: read('E2E_OTHER_COMPANY', 'Marca Demo Visual'),
};

if (!e2eEnv.email || !e2eEnv.password) {
  throw new Error(
    'Copia web/.env.e2e.example a web/.env.e2e y define E2E_EMAIL y E2E_PASSWORD.',
  );
}
