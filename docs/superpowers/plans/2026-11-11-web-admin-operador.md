# Panel web del operador — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir en `web/` el panel web del operador (React + TypeScript) que consume la API multiempresa existente para agenda, clientes, servicios, equipo, resumen, inventario de solo lectura y marca.

**Architecture:** SPA Vite con React Router, TanStack Query para estado del servidor, React Hook Form + Zod para formularios, Tailwind con tokens de marca y primitivas Radix. La sesión guarda solo el refresh token y el contexto de empresa; los datos de negocio viven únicamente en memoria y cada clave de consulta incluye la empresa activa. Cambiar de empresa siempre crea un contexto tenant nuevo y limpia la caché. La agenda usa la zona de la sucursal, un eje horario y alta desde hueco; el inventario es de solo lectura y descarga archivos autenticados como blob.

**Tech Stack:** React 18.3, TypeScript 5.7, Vite 6, React Router 6, TanStack Query 5, React Hook Form 7, Zod 3, Tailwind CSS 3.4, Radix Dialog, Vitest 3 + React Testing Library + MSW 2, Playwright 1.49.

**Spec:** `docs/superpowers/specs/2026-11-11-web-admin-operador-design.md`

**Specs complementarias:** `docs/superpowers/specs/2026-11-11-agenda-calendario-design.md` y `docs/superpowers/specs/2026-11-11-inventario-objetos-archivos-design.md`.

**Planes complementarios:** `docs/superpowers/plans/2026-11-11-agenda-calendario.md` y `docs/superpowers/plans/2026-11-11-inventario-objetos-archivos.md`.

## Global Constraints

- El backend sí cambia en esta fase: inventario (objetos y archivos) y `working-hours` en la sincronización móvil, según los planes complementarios. Las tareas 19A y 19B consumen esas extensiones. No se modifica ninguna API del núcleo web.
- Aislamiento por empresa: ninguna consulta se ejecuta sin `X-Tenant-Context`; cambiar de empresa siempre hace `POST /api/v1/tenant-contexts/` y luego `queryClient.clear()`. Cada clave de TanStack Query incluye `companyId`.
- No se persisten datos de negocio, bootstrap ni listados en `localStorage`/`sessionStorage`. Solo se persisten `agenda.web.refresh` (refresh token), `agenda.web.session` (`{companyId, contextId, companyName}`) y la preferencia visual `agenda.web.theme` (UI, no negocio).
- Toda la interfaz está en español. Fechas de calendario en la zona horaria de la sucursal seleccionada.
- Modo claro y oscuro en todas las pantallas; contraste AA, foco visible, navegación por teclado, diálogos con foco atrapado.
- Diseño para 1280 px y usable desde 768 px; no hay diseño móvil dedicado.
- Permisos: un trabajador usa `bookings.own.read`/`bookings.own.write`; la comprobación de agenda acepta `bookings.read` u `bookings.own.read` (y la variante `write`). Inventario exige `inventory.read`. Las funcionalidades apagadas del plan no aparecen en la navegación.
- **Commits:** Carlos no autorizó commits. Los pasos de commit están documentados, pero durante la ejecución hay que detenerse y pedir autorización antes de ejecutar cada `git commit`.
- Node.js 24 está disponible. No se instalan dependencias globales; todo queda en `web/package.json`.

---

## Estructura de archivos

```text
web/
  package.json                  dependencias y scripts
  tsconfig.json                 TypeScript estricto
  vite.config.ts                Vite + proxy /api y /media + Vitest
  tailwind.config.ts            tokens semánticos y de marca
  postcss.config.js             Tailwind + autoprefixer
  eslint.config.js              reglas TS, hooks y accesibilidad
  playwright.config.ts          E2E local contra Django
  index.html                    entrada del SPA
  .env.example                  VITE_API_BASE_URL
  src/
    main.tsx                    montaje de React
    App.tsx                     (temporal) smoke test del scaffold
    styles.css                  Tailwind y variables CSS claro/oscuro
    vite-env.d.ts               tipos de Vite
    api/
      types.ts                  DTOs compartidos
      client.ts                 fetch, cabeceras, refresh único, errores
      auth.ts                   login, refresh, empresas, contexto, bootstrap, logout
      agenda.ts                 reservas y disponibilidad
      customers.ts              clientes e historial
      services.ts               catálogo
      team.ts                   trabajadores, turnos, pausas, ausencias, bloqueos
      summary.ts                informes de ventas y caja
      inventory.ts              objetos, archivos, descarga y foto autenticadas
      branding.ts               marca y logo
      queryKeys.ts              claves de consulta con companyId
      runtime.ts                cliente real + gateways + instancias de dominio
    auth/
      sessionStore.ts           refresh y sesión en localStorage
      AuthProvider.tsx          estado de sesión, empresa y bootstrap
    components/ui/
      Button.tsx
      Field.tsx                 Field + Input + Select + Textarea
      Dialog.tsx                Radix Dialog + ConfirmDialog
      Badge.tsx
      EmptyState.tsx
      ErrorBanner.tsx
      PageHeader.tsx
      Pagination.tsx
      Skeleton.tsx
    features/
      auth/LoginPage.tsx
      companies/CompanyChooserPage.tsx
      agenda/AgendaPage.tsx
      agenda/AgendaCalendar.tsx
      agenda/BookingCreateDialog.tsx
      agenda/BookingDetailDialog.tsx
      customers/CustomersPage.tsx
      customers/CustomerFormDialog.tsx
      customers/CustomerHistoryDialog.tsx
      services/ServicesPage.tsx
      services/ServiceFormDialog.tsx
      team/WorkersSection.tsx
      team/WorkerFormDialog.tsx
      team/TeamPage.tsx
      team/ScheduleSection.tsx
      team/TimeOffSection.tsx
      team/BlockedSlotsSection.tsx
      summary/SummaryPage.tsx
      inventory/InventoryPage.tsx
      inventory/InventoryObjectsTab.tsx
      inventory/InventoryFilesTab.tsx
      branding/BrandingPage.tsx
    app/
      queryClient.ts
      providers.tsx
      router.tsx
      guards.tsx
      AppLayout.tsx
      HomeRedirect.tsx
    lib/
      permissions.ts            navegación y permisos
      dates.ts                  fechas y zonas horarias
      colors.ts                 contraste de marca
      format.ts                 moneda, textos y estados
      useDebouncedValue.ts
      useOnlineStatus.ts
    theme/
      ThemeProvider.tsx
    test/
      setup.ts
      server.ts
      factories.ts
  .env.test                     base fija de MSW para Vitest
  .env.e2e.example              variables de las pruebas Playwright
  .env.production.example       build de mismo origen
  e2e/
    global-setup.ts             sesión compartida de la suite
    support/api.ts              login y contexto tenant reales
    support/env.ts              lectura de .env.e2e
    support/session.ts          inyección y refresh simulado
    support/seed.ts             datos únicos por prueba
    auth.spec.ts
    agenda.spec.ts
    customers.spec.ts
    team.spec.ts
    summary.spec.ts
    branding.spec.ts
    isolation.spec.ts
    session.spec.ts
    a11y.spec.ts
    responsive.spec.ts
  deploy/
    nginx.conf.example
```

---

### Task 1: Scaffold del proyecto web

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/vite.config.ts`, `web/tailwind.config.ts`, `web/postcss.config.js`, `web/eslint.config.js`, `web/index.html`, `web/.env.example`, `web/.env.test`, `web/src/main.tsx`, `web/src/App.tsx`, `web/src/styles.css`, `web/src/vite-env.d.ts`, `web/src/test/setup.ts`, `web/src/test/server.ts`, `web/src/App.test.tsx`
- Modify: `.gitignore`

**Interfaces:**
- Produces: proyecto `web/` ejecutable con `npm run dev`, `npm run test`, `npm run lint` y `npm run build`; tokens CSS `--surface`, `--panel`, `--ink`, `--muted`, `--line`, `--brand-primary`, `--brand-secondary`, `--brand-fg`, `--brand-soft`, `--danger*`, `--success*`, `--warning*`, `--status-*`.

- [ ] **Step 1: Crear la configuración del proyecto**

`web/package.json`:

```json
{
  "name": "agenda-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "test": "vitest run",
    "test:watch": "vitest",
    "e2e": "playwright test",
    "e2e:install": "playwright install chromium"
  },
  "dependencies": {
    "@hookform/resolvers": "^3.9.1",
    "@radix-ui/react-dialog": "^1.1.4",
    "@tanstack/react-query": "^5.62.11",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-hook-form": "^7.54.2",
    "react-router-dom": "^6.28.1",
    "zod": "^3.24.1"
  },
  "devDependencies": {
    "@axe-core/playwright": "^4.10.1",
    "@eslint/js": "^9.17.0",
    "@playwright/test": "^1.49.1",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.1.0",
    "@testing-library/user-event": "^14.5.2",
    "@types/node": "^22.10.5",
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.17.0",
    "eslint-plugin-jsx-a11y": "^6.10.2",
    "eslint-plugin-react-hooks": "^5.1.0",
    "eslint-plugin-react-refresh": "^0.4.16",
    "globals": "^15.14.0",
    "jsdom": "^25.0.1",
    "msw": "^2.7.0",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.17",
    "typescript": "^5.7.2",
    "typescript-eslint": "^8.19.1",
    "vite": "^6.0.7",
    "vitest": "^3.2.7"
  }
}
```

`web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "Bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals", "node"]
  },
  "include": ["src", "e2e", "vite.config.ts", "tailwind.config.ts", "playwright.config.ts"]
}
```

`web/vite.config.ts`:

```ts
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/media': 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    globals: true,
  },
});
```

`web/tailwind.config.ts`:

```ts
import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: 'var(--surface)',
        panel: 'var(--panel)',
        ink: 'var(--ink)',
        muted: 'var(--muted)',
        line: 'var(--line)',
        brand: {
          DEFAULT: 'var(--brand-primary)',
          fg: 'var(--brand-fg)',
          soft: 'var(--brand-soft)',
        },
        danger: { DEFAULT: 'var(--danger)', soft: 'var(--danger-soft)' },
        success: { DEFAULT: 'var(--success)', soft: 'var(--success-soft)' },
        warning: { DEFAULT: 'var(--warning)', soft: 'var(--warning-soft)' },
        'status-scheduled-bg': 'var(--status-scheduled-bg)',
        'status-scheduled-fg': 'var(--status-scheduled-fg)',
        'status-confirmed-bg': 'var(--status-confirmed-bg)',
        'status-confirmed-fg': 'var(--status-confirmed-fg)',
        'status-completed-bg': 'var(--status-completed-bg)',
        'status-completed-fg': 'var(--status-completed-fg)',
        'status-canceled-bg': 'var(--status-canceled-bg)',
        'status-canceled-fg': 'var(--status-canceled-fg)',
        'status-noshow-bg': 'var(--status-noshow-bg)',
        'status-noshow-fg': 'var(--status-noshow-fg)',
      },
    },
  },
  plugins: [],
} satisfies Config;
```

`web/postcss.config.js`:

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

`web/eslint.config.js`:

```js
import js from '@eslint/js';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'playwright-report', 'test-results'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{jsx,tsx}'],
    ...jsxA11y.flatConfigs.recommended,
  },
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true, allowExportNames: ['useAuth', 'AuthContext', 'useTheme'] },
      ],
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
);
```

`web/index.html`:

```html
<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="color-scheme" content="light dark" />
    <title>AGENDA — Panel del operador</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`web/.env.example`:

```text
# URL absoluta de la API. Vacío usa el mismo origen.
VITE_API_BASE_URL=http://127.0.0.1:8000
```

`web/.env.test`:

```text
# Vitest usa MSW con esta base fija; no debe apuntar a un servidor real.
VITE_API_BASE_URL=http://api.test
```

`web/src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />
```

- [ ] **Step 2: Crear estilos con tokens claro/oscuro**

`web/src/styles.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --surface: #f1f5f9;
  --panel: #ffffff;
  --ink: #0f172a;
  --muted: #475569;
  --line: #cbd5e1;
  --brand-primary: #e50914;
  --brand-secondary: #8b0000;
  --brand-fg: #ffffff;
  --brand-soft: #fee2e2;
  --danger: #b91c1c;
  --danger-soft: #fee2e2;
  --success: #15803d;
  --success-soft: #dcfce7;
  --warning: #a16207;
  --warning-soft: #fef3c7;
  --status-scheduled-bg: #e0f2fe;
  --status-scheduled-fg: #075985;
  --status-confirmed-bg: #dcfce7;
  --status-confirmed-fg: #166534;
  --status-completed-bg: #e2e8f0;
  --status-completed-fg: #334155;
  --status-canceled-bg: #ffe4e6;
  --status-canceled-fg: #9f1239;
  --status-noshow-bg: #fef3c7;
  --status-noshow-fg: #92400e;
}

[data-theme='dark'] {
  --surface: #0b1120;
  --panel: #111827;
  --ink: #f8fafc;
  --muted: #cbd5e1;
  --line: #334155;
  --brand-soft: #3f1d1d;
  --danger: #fca5a5;
  --danger-soft: #450a0a;
  --success: #86efac;
  --success-soft: #052e16;
  --warning: #fcd34d;
  --warning-soft: #422006;
  --status-scheduled-bg: #0c4a6e;
  --status-scheduled-fg: #e0f2fe;
  --status-confirmed-bg: #14532d;
  --status-confirmed-fg: #dcfce7;
  --status-completed-bg: #334155;
  --status-completed-fg: #f1f5f9;
  --status-canceled-bg: #4c0519;
  --status-canceled-fg: #ffe4e6;
  --status-noshow-bg: #451a03;
  --status-noshow-fg: #fef3c7;
}

html,
body,
#root {
  min-height: 100%;
}

body {
  margin: 0;
  background: var(--surface);
  color: var(--ink);
  font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
}
```

- [ ] **Step 3: Crear entrada y smoke test**

`web/src/App.tsx`:

```tsx
export function App() {
  return (
    <main className="p-8">
      <h1 className="text-2xl font-semibold text-ink">AGENDA — Panel del operador</h1>
    </main>
  );
}
```

`web/src/main.tsx`:

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

`web/src/test/server.ts`:

```ts
import { setupServer } from 'msw/node';

export const server = setupServer();
```

`web/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest';

import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll } from 'vitest';

import { server } from './server';

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver ??= ResizeObserverMock;
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
if (!HTMLElement.prototype.hasPointerCapture) {
  HTMLElement.prototype.hasPointerCapture = () => false;
  HTMLElement.prototype.setPointerCapture = () => {};
  HTMLElement.prototype.releasePointerCapture = () => {};
}

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  localStorage.clear();
  sessionStorage.clear();
});
afterAll(() => server.close());
```

`web/src/App.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';

import { App } from './App';

test('muestra el nombre del panel', () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: /panel del operador/i })).toBeInTheDocument();
});
```

- [ ] **Step 4: Instalar dependencias y verificar el scaffold**

Run:

```bash
cd web
npm install
npm run test
npm run lint
npm run build
```

Expected: `npm install` sin errores; 1 test PASS; lint sin errores; build genera `web/dist/`.

- [ ] **Step 5: Ignorar artefactos del panel**

Append to `.gitignore`:

```gitignore
web/node_modules/
web/dist/
web/.env
web/.env.local
web/playwright-report/
web/test-results/
```

- [ ] **Step 6: Commit (requiere autorización explícita de Carlos)**

```bash
git add .gitignore web
git commit -m "chore(web): scaffold Vite + React + Tailwind app"
```

---

### Task 2: Cliente HTTP con refresh único y errores normalizados

**Files:**
- Create: `web/src/api/types.ts`, `web/src/api/client.ts`, `web/src/api/client.test.ts`

**Interfaces:**
- Produces:
  - `ApiError` con `status: number`, `message: string`, `fields?: Record<string, string[]>`, `requestId?: string`.
  - `ApiClient` con `get<T>`, `post<T>`, `postForm<T>`, `patch<T>`, `delete<T>`, `request<T>`, `configureRefresh(handler)`, `configureUnauthorized(handler)`.
  - Tipos base `User`, `CompanySummary`, `Bootstrap`, `Paginated<T>`, `LoginResponse`, `RefreshResponse`, `TenantContextResponse`.

- [ ] **Step 1: Escribir las pruebas del cliente**

`web/src/api/client.test.ts`:

```ts
import { http, HttpResponse } from 'msw';
import { describe, expect, test, vi } from 'vitest';

import { server } from '../test/server';
import { ApiClient, ApiError } from './client';

function makeClient(overrides: Partial<ConstructorParameters<typeof ApiClient>[0]> = {}) {
  return new ApiClient({
    baseUrl: 'http://api.test',
    getAccessToken: () => 'access-1',
    getTenantContextId: () => 'ctx-1',
    ...overrides,
  });
}

describe('ApiClient', () => {
  test('envía autenticación, contexto tenant y query params', async () => {
    let capturedUrl = '';
    server.use(
      http.get('http://api.test/api/v1/bookings/', ({ request }) => {
        capturedUrl = request.url;
        expect(request.headers.get('Authorization')).toBe('Bearer access-1');
        expect(request.headers.get('X-Tenant-Context')).toBe('ctx-1');
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );

    const response = await makeClient().get('/api/v1/bookings/', { search: 'ana', page: 2 });

    expect(response).toEqual({ count: 0, next: null, previous: null, results: [] });
    expect(capturedUrl).toContain('search=ana');
    expect(capturedUrl).toContain('page=2');
  });

  test('normaliza errores de validación por campo', async () => {
    server.use(
      http.post('http://api.test/api/v1/bookings/', () =>
        HttpResponse.json(
          { detail: 'Datos inválidos', start_at: ['La reserva debe ser futura.'] },
          { status: 400 },
        ),
      ),
    );

    const promise = makeClient().post('/api/v1/bookings/', { start_at: 'ayer' });

    await expect(promise).rejects.toMatchObject({
      status: 400,
      message: 'Datos inválidos',
      fields: { start_at: ['La reserva debe ser futura.'] },
    });
  });

  test('conserva el mensaje de un conflicto 409', async () => {
    server.use(
      http.post('http://api.test/api/v1/bookings/booking-1/reschedule/', () =>
        HttpResponse.json({ detail: 'El horario seleccionado ya no está disponible.' }, { status: 409 }),
      ),
    );

    await expect(
      makeClient().post('/api/v1/bookings/booking-1/reschedule/', {}),
    ).rejects.toMatchObject({
      status: 409,
      message: 'El horario seleccionado ya no está disponible.',
    });
  });

  test('convierte un fallo de red en status 0', async () => {
    const client = makeClient({
      fetchImpl: async () => {
        throw new TypeError('Failed to fetch');
      },
    });

    await expect(client.get('/api/v1/companies/mine/')).rejects.toMatchObject({
      status: 0,
      message: 'Sin conexión con el servidor.',
    });
  });

  test('hace un solo refresh para solicitudes concurrentes con 401', async () => {
    let access = 'expired';
    let refreshCalls = 0;
    const client = makeClient({ getAccessToken: () => access });
    client.configureRefresh(async () => {
      refreshCalls += 1;
      await new Promise((resolve) => setTimeout(resolve, 20));
      access = 'fresh';
      return 'fresh';
    });
    server.use(
      http.get('http://api.test/api/v1/customers/', ({ request }) =>
        request.headers.get('Authorization') === 'Bearer fresh'
          ? HttpResponse.json({ count: 0, next: null, previous: null, results: [] })
          : HttpResponse.json({ detail: 'Token vencido.' }, { status: 401 }),
      ),
    );

    const [first, second] = await Promise.all([
      client.get('/api/v1/customers/'),
      client.get('/api/v1/customers/'),
    ]);

    expect(refreshCalls).toBe(1);
    expect(first).toEqual({ count: 0, next: null, previous: null, results: [] });
    expect(second).toEqual(first);
  });

  test('notifica el cierre de sesión cuando el refresh falla', async () => {
    const unauthorized = vi.fn();
    const client = makeClient();
    client.configureRefresh(async () => {
      throw new ApiError(401, 'Sesión expirada.');
    });
    client.configureUnauthorized(unauthorized);
    server.use(
      http.get('http://api.test/api/v1/customers/', () =>
        HttpResponse.json({ detail: 'Token vencido.' }, { status: 401 }),
      ),
    );

    await expect(client.get('/api/v1/customers/')).rejects.toMatchObject({ status: 401 });
    expect(unauthorized).toHaveBeenCalledTimes(1);
  });

  test('maneja 204 sin intentar leer JSON', async () => {
    server.use(
      http.delete('http://api.test/api/v1/customers/customer-1/', () => new HttpResponse(null, { status: 204 })),
    );

    await expect(makeClient().delete('/api/v1/customers/customer-1/')).resolves.toBeUndefined();
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

Run: `cd web && npm run test -- src/api/client.test.ts`

Expected: FAIL porque `./client` no existe.

- [ ] **Step 3: Crear los tipos compartidos**

`web/src/api/types.ts`:

```ts
export type UUID = string;
export type ISODate = string;
export type ISODateTime = string;
export type ThemeMode = 'light' | 'dark';

export type User = {
  id: UUID;
  email: string;
  first_name: string;
  last_name: string;
  is_saas_admin: boolean;
};

export type CompanySummary = {
  id: UUID;
  name: string;
  display_name: string;
  slug: string;
  logo_url: string;
  primary_color: string;
  secondary_color: string;
  theme_mode: ThemeMode;
  booking_url: string;
  status: string;
};

export type Branch = {
  id: UUID;
  company: UUID;
  name: string;
  code: string;
  address: string;
  timezone: string;
  active: boolean;
};

export type Membership = {
  id: UUID;
  role: string;
  role_display: string;
};

export type BootstrapCompany = CompanySummary & {
  legal_name?: string;
  tax_identifier?: string;
};

export type Bootstrap = {
  api_version: string;
  server_time: string;
  user: User;
  company: BootstrapCompany;
  membership: Membership;
  worker: { id: UUID; name: string } | null;
  companies: CompanySummary[];
  permissions: string[];
  features: Record<string, boolean>;
  modules: Record<string, boolean>;
  billing_state: string;
  branches: Branch[];
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type LoginResponse = {
  access: string;
  refresh: string;
  user: User;
};

export type RefreshResponse = {
  access: string;
  refresh?: string;
};

export type TenantContextResponse = {
  id: string;
  company: UUID;
  company_name: string;
  expires_at: string;
};
```

- [ ] **Step 4: Implementar el cliente**

`web/src/api/client.ts`:

```ts
export type QueryParams = Record<string, string | number | boolean | null | undefined>;

export type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  formData?: FormData;
  query?: QueryParams;
  auth?: boolean;
  retry?: boolean;
};

type ApiClientConfig = {
  baseUrl?: string;
  getAccessToken: () => string | null;
  getTenantContextId: () => string | null;
  fetchImpl?: typeof fetch;
};

export class ApiError extends Error {
  readonly status: number;
  readonly fields?: Record<string, string[]>;
  readonly requestId?: string;

  constructor(status: number, message: string, fields?: Record<string, string[]>, requestId?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fields = fields;
    this.requestId = requestId;
  }
}

function normalizeError(status: number, payload: unknown): ApiError {
  let message = 'Ocurrió un error inesperado.';
  let fields: Record<string, string[]> | undefined;
  let requestId: string | undefined;

  if (payload && typeof payload === 'object') {
    const data = payload as Record<string, unknown>;
    if (typeof data.detail === 'string') {
      message = data.detail;
    }
    Object.entries(data).forEach(([key, value]) => {
      if (key === 'detail') return;
      const messages = Array.isArray(value)
        ? value.filter((item): item is string => typeof item === 'string')
        : typeof value === 'string'
          ? [value]
          : [];
      if (messages.length > 0) {
        fields = { ...fields, [key]: messages };
        if (message === 'Ocurrió un error inesperado.') message = messages[0];
      }
    });
    if (typeof data.request_id === 'string') requestId = data.request_id;
  }

  if (status === 401 && message === 'Ocurrió un error inesperado.') message = 'Sesión expirada.';
  if (status === 403 && message === 'Ocurrió un error inesperado.') message = 'No tienes permiso para esta acción.';
  if (status === 0) message = 'Sin conexión con el servidor.';

  return new ApiError(status, message, fields, requestId);
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly getAccessToken: () => string | null;
  private readonly getTenantContextId: () => string | null;
  private readonly fetchImpl: typeof fetch;
  private refreshHandler?: () => Promise<string>;
  private unauthorizedHandler?: () => void;
  private refreshPromise?: Promise<string>;

  constructor(config: ApiClientConfig) {
    this.baseUrl = (config.baseUrl ?? '').replace(/\/+$/, '');
    this.getAccessToken = config.getAccessToken;
    this.getTenantContextId = config.getTenantContextId;
    this.fetchImpl = config.fetchImpl ?? fetch;
  }

  configureRefresh(handler: () => Promise<string>) {
    this.refreshHandler = handler;
  }

  configureUnauthorized(handler: () => void) {
    this.unauthorizedHandler = handler;
  }

  get<T>(path: string, query?: QueryParams): Promise<T> {
    return this.request<T>(path, { query });
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, { method: 'POST', body });
  }

  postForm<T>(path: string, formData: FormData): Promise<T> {
    return this.request<T>(path, { method: 'POST', formData });
  }

  patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, { method: 'PATCH', body });
  }

  delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'DELETE' });
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { method = 'GET', body, formData, query, auth = true, retry = true } = options;
    const origin = this.baseUrl || window.location.origin;
    const url = new URL(`${origin}${path}`);
    Object.entries(query ?? {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    });

    const headers: Record<string, string> = { Accept: 'application/json' };
    if (body !== undefined && !formData) headers['Content-Type'] = 'application/json';
    if (auth) {
      const access = this.getAccessToken();
      if (access) headers.Authorization = `Bearer ${access}`;
      const contextId = this.getTenantContextId();
      if (contextId) headers['X-Tenant-Context'] = contextId;
    }

    let response: Response;
    try {
      response = await this.fetchImpl(url.toString(), {
        method,
        headers,
        body: formData ?? (body === undefined ? undefined : JSON.stringify(body)),
      });
    } catch {
      throw normalizeError(0, null);
    }

    if (response.status === 401 && auth && retry) {
      try {
        await this.refreshOnce();
      } catch {
        this.unauthorizedHandler?.();
        throw new ApiError(401, 'Sesión expirada.');
      }
      return this.request<T>(path, { ...options, retry: false });
    }

    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw normalizeError(response.status, payload);
    }

    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  private refreshOnce(): Promise<string> {
    if (!this.refreshPromise) {
      const promise = (async () => {
        if (!this.refreshHandler) throw new ApiError(401, 'Sesión expirada.');
        return this.refreshHandler();
      })();
      this.refreshPromise = promise.finally(() => {
        this.refreshPromise = undefined;
      });
    }
    return this.refreshPromise;
  }
}
```

- [ ] **Step 5: Ejecutar las pruebas y verificar**

Run: `cd web && npm run test -- src/api/client.test.ts`

Expected: 7 tests PASS.

- [ ] **Step 6: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/api
git commit -m "feat(web): add API client with tenant headers and single-flight refresh"
```

---

### Task 3: Almacenamiento de sesión y AuthProvider

**Files:**
- Create: `web/src/auth/sessionStore.ts`, `web/src/auth/AuthProvider.tsx`, `web/src/auth/AuthProvider.test.tsx`, `web/src/api/auth.ts`, `web/src/api/runtime.ts`, `web/src/lib/permissions.ts`, `web/src/test/factories.ts`

**Interfaces:**
- Consumes: `ApiClient`, `ApiError`, tipos de `types.ts`.
- Produces:
  - `SessionStore` y `localSessionStore` con claves `agenda.web.refresh` y `agenda.web.session`.
  - `AuthGateway` (`login`, `refresh`, `companies`, `createContext`, `bootstrap`, `logout`).
  - `AuthProvider` con estado `'loading' | 'anonymous' | 'choosingCompany' | 'ready'` y métodos `login`, `selectCompany`, `logout`, `refreshBootstrap`, `can`, `hasFeature`.
  - `AuthContext` exportado para pruebas de componentes.
  - `sessionRuntime`, `apiClient`, `authGateway` en `runtime.ts`.

- [ ] **Step 1: Escribir las pruebas del AuthProvider**

`web/src/test/factories.ts`:

```ts
import { vi } from 'vitest';

import type { AuthGateway } from '../auth/AuthProvider';
import type { SessionStore } from '../auth/sessionStore';
import type { Bootstrap, CompanySummary, User } from '../api/types';

export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 'user-1',
    email: 'owner@agenda.app',
    first_name: 'Carlos',
    last_name: 'Pérez',
    is_saas_admin: false,
    ...overrides,
  };
}

export function makeCompany(overrides: Partial<CompanySummary> = {}): CompanySummary {
  return {
    id: 'company-a',
    name: 'Estudio Aurora',
    display_name: 'Estudio Aurora',
    slug: 'estudio-aurora',
    logo_url: '',
    primary_color: '#10B981',
    secondary_color: '#065F46',
    theme_mode: 'light',
    booking_url: '/b/estudio-aurora/',
    status: 'active',
    ...overrides,
  };
}

export function makeBootstrap(overrides: Partial<Bootstrap> = {}): Bootstrap {
  return {
    api_version: 'v1',
    server_time: '2026-11-11T12:00:00Z',
    user: makeUser(),
    company: makeCompany(),
    membership: { id: 'membership-1', role: 'owner', role_display: 'Propietario' },
    worker: null,
    companies: [makeCompany()],
    permissions: [
      'bookings.read',
      'bookings.write',
      'customers.read',
      'customers.write',
      'catalog.read',
      'catalog.write',
      'workforce.read',
      'workforce.write',
      'reports.read',
      'company.manage',
      'branches.read',
      'branches.manage',
      'subscription.read',
      'subscription.manage',
    ],
    features: {
      bookings: true,
      customers: true,
      catalog: true,
      workforce: true,
      inventory: false,
      sales: false,
      reports: true,
      branches: true,
      workers: true,
    },
    modules: { agenda: true, customers: true, inventory: false, subscription: false },
    billing_state: 'usable',
    branches: [
      {
        id: 'branch-1',
        company: 'company-a',
        name: 'Providencia',
        code: 'PROV',
        address: 'Av. Providencia 123',
        timezone: 'America/Santiago',
        active: true,
      },
    ],
    ...overrides,
  };
}

export function makeGateway(overrides: Partial<AuthGateway> = {}): AuthGateway {
  return {
    login: vi.fn(
      overrides.login ??
        (async () => ({ access: 'access-a', refresh: 'refresh-a', user: makeUser() })),
    ),
    refresh: vi.fn(overrides.refresh ?? (async () => ({ access: 'access-r', refresh: 'refresh-r' }))),
    companies: vi.fn(overrides.companies ?? (async () => [makeCompany()])),
    createContext: vi.fn(
      overrides.createContext ??
        (async (companyId) => ({
          id: `ctx-${companyId}`,
          company: companyId,
          company_name: 'Demo',
          expires_at: '2026-11-11T20:00:00Z',
        })),
    ),
    bootstrap: vi.fn(overrides.bootstrap ?? (async () => makeBootstrap())),
    logout: vi.fn(overrides.logout ?? (async () => undefined)),
  };
}

export function createMemorySessionStore(
  initial: {
    refresh?: string | null;
    session?: { companyId: string; contextId: string; companyName: string } | null;
  } = {},
): SessionStore & {
  state: {
    refresh: string | null;
    session: { companyId: string; contextId: string; companyName: string } | null;
  };
} {
  const state = {
    refresh: initial.refresh ?? null,
    session: initial.session ?? null,
  };
  return {
    state,
    readRefresh: () => state.refresh,
    writeRefresh: (value) => {
      state.refresh = value;
    },
    readSession: () => state.session,
    writeSession: (value) => {
      state.session = value;
    },
    clear: () => {
      state.refresh = null;
      state.session = null;
    },
  };
}
```

`web/src/auth/AuthProvider.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { describe, expect, test, vi } from 'vitest';

import { ApiError } from '../api/client';
import type { CompanySummary } from '../api/types';
import { createMemorySessionStore, makeBootstrap, makeCompany, makeGateway } from '../test/factories';
import { AuthProvider, useAuth } from './AuthProvider';
import type { SessionStore } from './sessionStore';

function Probe() {
  const auth = useAuth();
  const demo: CompanySummary = makeCompany({ id: 'company-b', name: 'Marca Demo Visual' });
  return (
    <div>
      <span data-testid="status">{auth.status}</span>
      <span data-testid="company">{auth.company?.name ?? ''}</span>
      <span data-testid="can-write">{auth.can('bookings.write') ? 'si' : 'no'}</span>
      <button onClick={() => auth.selectCompany(demo)}>cambiar</button>
      <button onClick={() => auth.logout()}>salir</button>
      <button onClick={() => auth.login('owner@agenda.app', 'Secreta2026!')}>entrar</button>
    </div>
  );
}

function renderAuth(
  store: SessionStore,
  gateway = makeGateway(),
  runtime = { accessToken: null as string | null, tenantContextId: null as string | null },
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const ui: ReactNode = (
    <QueryClientProvider client={queryClient}>
      <AuthProvider gateway={gateway} store={store} runtime={runtime}>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>
  );
  return { queryClient, runtime, ...render(ui) };
}

describe('AuthProvider', () => {
  test('restaura la sesión reutilizando el contexto guardado', async () => {
    const store = createMemorySessionStore({
      refresh: 'refresh-old',
      session: { companyId: 'company-a', contextId: 'ctx-old', companyName: 'Estudio Aurora' },
    });
    const gateway = makeGateway();
    renderAuth(store, gateway);

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'));

    expect(gateway.refresh).toHaveBeenCalledWith('refresh-old');
    expect(gateway.createContext).not.toHaveBeenCalled();
    expect(screen.getByTestId('company')).toHaveTextContent('Estudio Aurora');
    expect(store.state.session?.contextId).toBe('ctx-old');
  });

  test('si el contexto guardado no es válido selecciona la única empresa accesible', async () => {
    const store = createMemorySessionStore({
      refresh: 'refresh-old',
      session: { companyId: 'company-a', contextId: 'ctx-caducado', companyName: 'Estudio Aurora' },
    });
    const bootstrap = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(403, 'Contexto inválido.'))
      .mockResolvedValueOnce(makeBootstrap());
    const gateway = makeGateway({ bootstrap, companies: async () => [makeCompany()] });
    renderAuth(store, gateway);

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'));

    expect(gateway.createContext).toHaveBeenCalledWith('company-a');
    expect(store.state.session?.contextId).toBe('ctx-company-a');
  });

  test('cambiar de empresa crea un contexto nuevo y limpia la caché de consultas', async () => {
    const store = createMemorySessionStore({ refresh: 'refresh-1' });
    const bootstrap = makeBootstrap();
    const gateway = makeGateway({
      bootstrap: async (): Promise<ReturnType<typeof makeBootstrap>> => bootstrap,
      createContext: async (companyId) => ({
        id: `ctx-${companyId}`,
        company: companyId,
        company_name: 'Demo',
        expires_at: '2026-11-11T20:00:00Z',
      }),
    });
    const { queryClient } = renderAuth(store, gateway);
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'));

    queryClient.setQueryData(['bookings', 'company-a', {}], [{ id: 'booking-1' }]);
    await userEvent.click(screen.getByRole('button', { name: 'cambiar' }));

    await waitFor(() => expect(gateway.createContext).toHaveBeenCalledWith('company-b'));
    expect(queryClient.getQueryData(['bookings', 'company-a', {}])).toBeUndefined();
    expect(store.state.session?.companyId).toBe('company-b');
  });

  test('logout limpia tokens, sesión y caché', async () => {
    const store = createMemorySessionStore({ refresh: 'refresh-1' });
    const gateway = makeGateway();
    const { queryClient } = renderAuth(store, gateway);
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'));
    queryClient.setQueryData(['customers', 'company-a', {}], [{ id: 'customer-1' }]);

    await userEvent.click(screen.getByRole('button', { name: 'salir' }));

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'));
    expect(store.state.refresh).toBeNull();
    expect(store.state.session).toBeNull();
    expect(queryClient.getQueryData(['customers', 'company-a', {}])).toBeUndefined();
  });

  test('si el refresh falla al iniciar, deja la sesión anónima', async () => {
    const store = createMemorySessionStore({ refresh: 'refresh-roto' });
    const gateway = makeGateway({
      refresh: async () => {
        throw new ApiError(401, 'Token inválido.');
      },
    });
    renderAuth(store, gateway);

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'));
    expect(store.state.refresh).toBeNull();
  });

  test('el login con una sola empresa selecciona la empresa automáticamente', async () => {
    const store = createMemorySessionStore();
    const gateway = makeGateway({ companies: async () => [makeCompany()] });
    renderAuth(store, gateway);
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'));

    await userEvent.click(screen.getByRole('button', { name: 'entrar' }));

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'));
    expect(gateway.createContext).toHaveBeenCalledWith('company-a');
    expect(store.state.refresh).toBe('refresh-a');
  });

  test('un evento de sesión expirada limpia el estado', async () => {
    const store = createMemorySessionStore({ refresh: 'refresh-1' });
    renderAuth(store, makeGateway());
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'));

    act(() => {
      window.dispatchEvent(new Event('agenda:session-expired'));
    });

    expect(screen.getByTestId('status')).toHaveTextContent('anonymous');
    expect(store.state.refresh).toBeNull();
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

Run: `cd web && npm run test -- src/auth/AuthProvider.test.tsx`

Expected: FAIL porque `./AuthProvider` y `./sessionStore` no existen.

- [ ] **Step 3: Implementar el almacenamiento**

`web/src/auth/sessionStore.ts`:

```ts
export const REFRESH_KEY = 'agenda.web.refresh';
export const SESSION_KEY = 'agenda.web.session';

export type StoredSession = {
  companyId: string;
  contextId: string;
  companyName: string;
};

export type SessionStore = {
  readRefresh(): string | null;
  writeRefresh(value: string | null): void;
  readSession(): StoredSession | null;
  writeSession(value: StoredSession | null): void;
  clear(): void;
};

function readJson<T>(key: string): T | null {
  const raw = localStorage.getItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    localStorage.removeItem(key);
    return null;
  }
}

export const localSessionStore: SessionStore = {
  readRefresh: () => localStorage.getItem(REFRESH_KEY),
  writeRefresh: (value) => {
    if (value) localStorage.setItem(REFRESH_KEY, value);
    else localStorage.removeItem(REFRESH_KEY);
  },
  readSession: () => readJson<StoredSession>(SESSION_KEY),
  writeSession: (value) => {
    if (value) localStorage.setItem(SESSION_KEY, JSON.stringify(value));
    else localStorage.removeItem(SESSION_KEY);
  },
  clear: () => {
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(SESSION_KEY);
  },
};
```

- [ ] **Step 4: Crear el verificador de permisos compartido**

`web/src/lib/permissions.ts`:

```ts
export function allows(permissions: string[], required: string): boolean {
  if (required === 'bookings.read') {
    return permissions.includes('bookings.read') || permissions.includes('bookings.own.read');
  }
  if (required === 'bookings.write') {
    return permissions.includes('bookings.write') || permissions.includes('bookings.own.write');
  }
  return permissions.includes(required);
}
```

- [ ] **Step 5: Implementar el gateway de autenticación**

`web/src/api/auth.ts`:

```ts
import type { AuthGateway } from '../auth/AuthProvider';
import type { ApiClient } from './client';
import type {
  Bootstrap,
  CompanySummary,
  LoginResponse,
  RefreshResponse,
  TenantContextResponse,
} from './types';

export function createAuthGateway(client: ApiClient): AuthGateway {
  return {
    login: (email, password) =>
      client.post<LoginResponse>('/api/v1/auth/token/', { email, password }),
    refresh: (refresh) =>
      client.post<RefreshResponse>('/api/v1/auth/token/refresh/', { refresh }),
    companies: () => client.get<CompanySummary[]>('/api/v1/companies/mine/'),
    createContext: (companyId) =>
      client.post<TenantContextResponse>('/api/v1/tenant-contexts/', { company: companyId }),
    bootstrap: () => client.get<Bootstrap>('/api/v1/mobile/bootstrap/'),
    logout: (refresh) => client.post<void>('/api/v1/auth/logout/', { refresh }),
  };
}
```

`web/src/api/runtime.ts`:

```ts
import { localSessionStore } from '../auth/sessionStore';
import { createAuthGateway } from './auth';
import { ApiClient, ApiError } from './client';

export const sessionRuntime: {
  accessToken: string | null;
  tenantContextId: string | null;
} = {
  accessToken: null,
  tenantContextId: null,
};

export const apiClient = new ApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000',
  getAccessToken: () => sessionRuntime.accessToken,
  getTenantContextId: () => sessionRuntime.tenantContextId,
});

export const authGateway = createAuthGateway(apiClient);

apiClient.configureRefresh(async () => {
  const refresh = localSessionStore.readRefresh();
  if (!refresh) throw new ApiError(401, 'Sesión expirada.');
  const data = await authGateway.refresh(refresh);
  sessionRuntime.accessToken = data.access;
  if (data.refresh) localSessionStore.writeRefresh(data.refresh);
  return data.access;
});

apiClient.configureUnauthorized(() => {
  window.dispatchEvent(new Event('agenda:session-expired'));
});
```

- [ ] **Step 6: Implementar el AuthProvider**

`web/src/auth/AuthProvider.tsx`:

```tsx
import { useQueryClient } from '@tanstack/react-query';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { ApiError } from '../api/client';
import type {
  Bootstrap,
  BootstrapCompany,
  CompanySummary,
  LoginResponse,
  RefreshResponse,
  TenantContextResponse,
  User,
} from '../api/types';
import { allows } from '../lib/permissions';
import type { SessionStore } from './sessionStore';

export type AuthStatus = 'loading' | 'anonymous' | 'choosingCompany' | 'ready';

export type AuthGateway = {
  login(email: string, password: string): Promise<LoginResponse>;
  refresh(refresh: string): Promise<RefreshResponse>;
  companies(): Promise<CompanySummary[]>;
  createContext(companyId: string): Promise<TenantContextResponse>;
  bootstrap(): Promise<Bootstrap>;
  logout(refresh: string): Promise<void>;
};

type Runtime = {
  accessToken: string | null;
  tenantContextId: string | null;
};

export type AuthContextValue = {
  status: AuthStatus;
  user: User | null;
  companies: CompanySummary[];
  company: BootstrapCompany | null;
  bootstrap: Bootstrap | null;
  permissions: string[];
  error: string | null;
  login(email: string, password: string): Promise<void>;
  selectCompany(company: CompanySummary): Promise<void>;
  logout(): Promise<void>;
  refreshBootstrap(): Promise<void>;
  can(required: string): boolean;
  hasFeature(code: string): boolean;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Ocurrió un error inesperado.';
}

type Props = {
  children: ReactNode;
  gateway: AuthGateway;
  store: SessionStore;
  runtime: Runtime;
};

export function AuthProvider({ children, gateway, store, runtime }: Props) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<User | null>(null);
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [company, setCompany] = useState<BootstrapCompany | null>(null);
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [error, setError] = useState<string | null>(null);

  const clearLocalSession = useCallback(() => {
    runtime.accessToken = null;
    runtime.tenantContextId = null;
    store.clear();
    queryClient.clear();
    setUser(null);
    setCompanies([]);
    setCompany(null);
    setBootstrap(null);
    setError(null);
  }, [queryClient, runtime, store]);

  const applyBootstrap = useCallback((data: Bootstrap) => {
    setUser(data.user);
    setCompany(data.company);
    setBootstrap(data);
  }, []);

  const activateCompany = useCallback(
    async (target: CompanySummary) => {
      setStatus('loading');
      setError(null);
      const context = await gateway.createContext(target.id);
      runtime.tenantContextId = context.id;
      store.writeSession({
        companyId: target.id,
        contextId: context.id,
        companyName: target.display_name || target.name,
      });
      queryClient.clear();
      const data = await gateway.bootstrap();
      applyBootstrap(data);
      setStatus('ready');
    },
    [applyBootstrap, gateway, queryClient, runtime, store],
  );

  useEffect(() => {
    let cancelled = false;

    async function restore() {
      const refresh = store.readRefresh();
      if (!refresh) {
        if (!cancelled) setStatus('anonymous');
        return;
      }
      try {
        const tokens = await gateway.refresh(refresh);
        if (cancelled) return;
        runtime.accessToken = tokens.access;
        if (tokens.refresh) store.writeRefresh(tokens.refresh);

        const list = await gateway.companies();
        if (cancelled) return;
        setCompanies(list);

        const stored = store.readSession();
        if (stored) {
          const match = list.find((item) => item.id === stored.companyId);
          if (match) {
            runtime.tenantContextId = stored.contextId;
            try {
              const data = await gateway.bootstrap();
              if (cancelled) return;
              applyBootstrap(data);
              setStatus('ready');
              return;
            } catch (restoreError) {
              if (!(restoreError instanceof ApiError) || ![401, 403].includes(restoreError.status)) {
                throw restoreError;
              }
              runtime.tenantContextId = null;
              store.writeSession(null);
            }
          } else {
            store.writeSession(null);
          }
        }

        if (list.length === 1) {
          await activateCompany(list[0]);
          return;
        }
        if (list.length === 0) {
          clearLocalSession();
          setStatus('anonymous');
          setError('La cuenta no tiene empresas activas.');
          return;
        }
        runtime.tenantContextId = null;
        setStatus('choosingCompany');
      } catch (restoreError) {
        if (cancelled) return;
        clearLocalSession();
        setStatus('anonymous');
        if (restoreError instanceof ApiError && restoreError.status !== 401) {
          setError(restoreError.message);
        }
      }
    }

    void restore();
    return () => {
      cancelled = true;
    };
  }, [activateCompany, applyBootstrap, clearLocalSession, gateway, runtime, store]);

  const login = useCallback(
    async (email: string, password: string) => {
      setStatus('loading');
      setError(null);
      try {
        const data = await gateway.login(email, password);
        runtime.accessToken = data.access;
        store.writeRefresh(data.refresh);
        setUser(data.user);
        const list = await gateway.companies();
        setCompanies(list);
        if (list.length === 1) {
          await activateCompany(list[0]);
        } else if (list.length === 0) {
          clearLocalSession();
          setStatus('anonymous');
          setError('La cuenta no tiene empresas activas.');
        } else {
          runtime.tenantContextId = null;
          store.writeSession(null);
          setStatus('choosingCompany');
        }
      } catch (loginError) {
        runtime.accessToken = null;
        store.writeRefresh(null);
        setError(messageOf(loginError));
        setStatus('anonymous');
        throw loginError;
      }
    },
    [activateCompany, clearLocalSession, gateway, runtime, store],
  );

  const selectCompany = useCallback(
    async (target: CompanySummary) => {
      try {
        await activateCompany(target);
      } catch (selectError) {
        setError(messageOf(selectError));
        setStatus(company ? 'ready' : 'choosingCompany');
        throw selectError;
      }
    },
    [activateCompany, company],
  );

  const logout = useCallback(async () => {
    const refresh = store.readRefresh();
    try {
      if (refresh) await gateway.logout(refresh);
    } catch {
      // El cierre local manda aunque el servidor no responda.
    }
    clearLocalSession();
    setStatus('anonymous');
  }, [clearLocalSession, gateway, store]);

  const refreshBootstrap = useCallback(async () => {
    const data = await gateway.bootstrap();
    applyBootstrap(data);
  }, [applyBootstrap, gateway]);

  useEffect(() => {
    const handler = () => {
      clearLocalSession();
      setStatus('anonymous');
    };
    window.addEventListener('agenda:session-expired', handler);
    return () => window.removeEventListener('agenda:session-expired', handler);
  }, [clearLocalSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      companies,
      company,
      bootstrap,
      permissions: bootstrap?.permissions ?? [],
      error,
      login,
      selectCompany,
      logout,
      refreshBootstrap,
      can: (required) => allows(bootstrap?.permissions ?? [], required),
      hasFeature: (code) => bootstrap?.features[code] ?? false,
    }),
    [bootstrap, companies, company, error, login, logout, refreshBootstrap, selectCompany, status, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth debe usarse dentro de AuthProvider.');
  return value;
}
```

- [ ] **Step 7: Ejecutar las pruebas y verificar**

Run: `cd web && npm run test -- src/auth/AuthProvider.test.tsx`

Expected: 7 tests PASS.

- [ ] **Step 8: Verificar tipos y lint**

Run:

```bash
cd web
npm run build
npm run lint
```

Expected: build y lint sin errores.

- [ ] **Step 9: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/api web/src/auth web/src/test
git commit -m "feat(web): add session storage and auth provider with company-scoped context"
```

---

### Task 4: Componentes UI reutilizables

**Files:**
- Create: `web/src/components/ui/Button.tsx`, `Field.tsx`, `Dialog.tsx`, `Badge.tsx`, `EmptyState.tsx`, `ErrorBanner.tsx`, `PageHeader.tsx`, `Pagination.tsx`, `Skeleton.tsx`, `web/src/components/ui/ui.test.tsx`

**Interfaces:**
- Produces:
  - `Button` (`variant`, `loading`, `loadingLabel`), `Input`, `Select`, `Textarea`, `Field`.
  - `Dialog` (`open`, `onOpenChange`, `title`, `description`, `footer`, `wide`), `ConfirmDialog`.
  - `Badge` (`tone`: `scheduled|confirmed|completed|canceled|no_show|active|inactive`).
  - `EmptyState`, `ErrorBanner`, `PageHeader`, `Pagination`, `Skeleton`.
  - `inputClass` exportado desde `Field.tsx`.

- [ ] **Step 1: Escribir las pruebas de los componentes**

`web/src/components/ui/ui.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, test, vi } from 'vitest';

import { Badge } from './Badge';
import { Button } from './Button';
import { ConfirmDialog, Dialog } from './Dialog';
import { Field, Input } from './Field';
import { Pagination } from './Pagination';

describe('Button', () => {
  test('se deshabilita y muestra el texto de carga', () => {
    render(
      <Button loading loadingLabel="Entrando…">
        Entrar
      </Button>,
    );
    const button = screen.getByRole('button', { name: 'Entrando…' });
    expect(button).toBeDisabled();
  });
});

describe('Field', () => {
  test('asocia etiqueta, error y campo', () => {
    render(
      <Field label="Correo" htmlFor="email" error="Correo inválido">
        <Input id="email" />
      </Field>,
    );
    expect(screen.getByLabelText('Correo')).toHaveAttribute('id', 'email');
    expect(screen.getByRole('alert')).toHaveTextContent('Correo inválido');
  });
});

describe('Dialog', () => {
  test('cierra con Escape y devuelve el foco', async () => {
    const onOpenChange = vi.fn();
    function Harness() {
      const [open, setOpen] = useState(true);
      return (
        <Dialog
          open={open}
          onOpenChange={(next) => {
            setOpen(next);
            onOpenChange(next);
          }}
          title="Detalle de reserva"
        >
          <p>Contenido</p>
        </Dialog>
      );
    }
    render(<Harness />);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await userEvent.keyboard('{Escape}');

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});

describe('ConfirmDialog', () => {
  test('ejecuta la confirmación', async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open
        onOpenChange={() => {}}
        title="Desactivar cliente"
        description="El cliente dejará de aparecer en el listado activo."
        confirmLabel="Desactivar"
        onConfirm={onConfirm}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Desactivar' }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});

describe('Pagination', () => {
  test('deshabilita anterior en la primera página y siguiente en la última', () => {
    const onPage = vi.fn();
    const { rerender } = render(<Pagination page={1} count={120} onPage={onPage} />);
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeEnabled();

    rerender(<Pagination page={3} count={120} onPage={onPage} />);
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeDisabled();
  });
});

describe('Badge', () => {
  test('muestra el texto y aplica el tono', () => {
    render(<Badge tone="confirmed">Confirmada</Badge>);
    expect(screen.getByText('Confirmada')).toHaveClass('bg-status-confirmed-bg');
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

Run: `cd web && npm run test -- src/components/ui/ui.test.tsx`

Expected: FAIL porque los componentes no existen.

- [ ] **Step 3: Implementar los componentes**

`web/src/components/ui/Button.tsx`:

```tsx
import type { ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

const styles: Record<Variant, string> = {
  primary: 'bg-brand text-brand-fg hover:opacity-90',
  secondary: 'border border-line bg-panel text-ink hover:bg-surface',
  ghost: 'text-ink hover:bg-surface',
  danger: 'bg-danger text-white hover:opacity-90',
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  loading?: boolean;
  loadingLabel?: string;
};

export function Button({
  variant = 'primary',
  loading = false,
  loadingLabel = 'Procesando…',
  className = '',
  disabled,
  children,
  ...props
}: Props) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
    >
      {loading ? loadingLabel : children}
    </button>
  );
}
```

`web/src/components/ui/Field.tsx`:

```tsx
import { forwardRef } from 'react';
import type {
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react';

export const inputClass =
  'w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink shadow-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand disabled:cursor-not-allowed disabled:opacity-60';

type FieldProps = {
  label: string;
  htmlFor: string;
  error?: string;
  hint?: string;
  className?: string;
  children: ReactNode;
};

export function Field({ label, htmlFor, error, hint, className = '', children }: FieldProps) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium text-ink">
        {label}
      </label>
      {children}
      {hint && !error ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
      {error ? (
        <p role="alert" className="mt-1 text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className = '', ...props }, ref) {
    return <input {...props} ref={ref} className={`${inputClass} ${className}`} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className = '', ...props }, ref) {
    return <select {...props} ref={ref} className={`${inputClass} ${className}`} />;
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className = '', ...props }, ref) {
    return <textarea {...props} ref={ref} className={`${inputClass} min-h-24 ${className}`} />;
  },
);

export function FormRow({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div {...props} className={`grid gap-4 sm:grid-cols-2 ${className}`} />;
}
```

`web/src/components/ui/Dialog.tsx`:

```tsx
import * as RadixDialog from '@radix-ui/react-dialog';
import type { ReactNode } from 'react';

import { Button } from './Button';

type DialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  footer?: ReactNode;
  wide?: boolean;
  children: ReactNode;
};

export function Dialog({ open, onOpenChange, title, description, footer, wide, children }: DialogProps) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <RadixDialog.Content
          className={`fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[92vw] ${wide ? 'max-w-4xl' : 'max-w-lg'} -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg bg-panel p-6 shadow-xl focus:outline-none`}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <RadixDialog.Title className="text-lg font-semibold text-ink">{title}</RadixDialog.Title>
              {description ? (
                <RadixDialog.Description className="mt-1 text-sm text-muted">
                  {description}
                </RadixDialog.Description>
              ) : null}
            </div>
            <RadixDialog.Close aria-label="Cerrar" className="rounded p-1 text-muted hover:bg-surface">
              <span aria-hidden="true">×</span>
            </RadixDialog.Close>
          </div>
          <div className="mt-4">{children}</div>
          {footer ? <div className="mt-6 flex justify-end gap-2">{footer}</div> : null}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

type ConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  loading?: boolean;
  danger?: boolean;
};

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onConfirm,
  loading = false,
  danger = true,
}: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Volver
          </Button>
          <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-sm text-muted">Esta acción quedará registrada en la auditoría.</p>
    </Dialog>
  );
}
```

`web/src/components/ui/Badge.tsx`:

```tsx
import type { ReactNode } from 'react';

export type BadgeTone =
  | 'scheduled'
  | 'confirmed'
  | 'completed'
  | 'canceled'
  | 'no_show'
  | 'active'
  | 'inactive';

const tones: Record<BadgeTone, string> = {
  scheduled: 'bg-status-scheduled-bg text-status-scheduled-fg',
  confirmed: 'bg-status-confirmed-bg text-status-confirmed-fg',
  completed: 'bg-status-completed-bg text-status-completed-fg',
  canceled: 'bg-status-canceled-bg text-status-canceled-fg',
  no_show: 'bg-status-noshow-bg text-status-noshow-fg',
  active: 'bg-success-soft text-success',
  inactive: 'bg-status-completed-bg text-status-completed-fg',
};

export function Badge({ tone, children }: { tone: BadgeTone; children: ReactNode }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}
```

`web/src/components/ui/EmptyState.tsx`:

```tsx
import type { ReactNode } from 'react';

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-panel p-8 text-center">
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted">{description}</p>
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}
```

`web/src/components/ui/ErrorBanner.tsx`:

```tsx
import { Button } from './Button';

export function ErrorBanner({
  message,
  onRetry,
  retryLabel = 'Reintentar',
}: {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-danger-soft px-4 py-3 text-sm text-danger">
      <span>{message}</span>
      {onRetry ? (
        <Button variant="secondary" onClick={onRetry}>
          {retryLabel}
        </Button>
      ) : null}
    </div>
  );
}
```

`web/src/components/ui/PageHeader.tsx`:

```tsx
import type { ReactNode } from 'react';

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold text-ink">{title}</h1>
        {description ? <p className="mt-1 text-sm text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </header>
  );
}
```

`web/src/components/ui/Pagination.tsx`:

```tsx
import { Button } from './Button';

export function Pagination({
  page,
  count,
  pageSize = 50,
  onPage,
}: {
  page: number;
  count: number;
  pageSize?: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  const from = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, count);

  return (
    <nav aria-label="Paginación" className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-muted">
      <span>{count === 0 ? 'Sin resultados' : `${from}–${to} de ${count}`}</span>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Anterior
        </Button>
        <Button variant="secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Siguiente
        </Button>
      </div>
    </nav>
  );
}
```

`web/src/components/ui/Skeleton.tsx`:

```tsx
export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div aria-label="Cargando" role="status" className="space-y-3">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="h-10 animate-pulse rounded-md bg-line" />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test -- src/components/ui/ui.test.tsx
npm run build
npm run lint
```

Expected: 6 tests PASS; build y lint sin errores.

- [ ] **Step 5: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/components
git commit -m "feat(web): add accessible UI primitives and status badge"
```

### Task 5: Tema de marca y navegación por permisos

**Files:**
- Create: `web/src/theme/ThemeProvider.tsx`, `web/src/theme/ThemeProvider.test.tsx`, `web/src/lib/colors.ts`, `web/src/lib/colors.test.ts`, `web/src/lib/permissions.test.ts`
- Modify: `web/src/lib/permissions.ts`

**Interfaces:**
- Consumes: `allows` de `lib/permissions.ts`.
- Produces:
  - `ThemeProvider({ children, companyMode })` y `useTheme()` con `{ mode, preference, setMode, toggleMode }`; persiste `agenda.web.theme` en `sessionStorage`.
  - `normalizeHex`, `hexToRgb`, `relativeLuminance`, `contrastRatio`, `readableForeground`, `applyBrandTheme` en `lib/colors.ts`.
  - `NAV_ITEMS`, `visibleNav(can, hasFeature, items?)` y `firstAllowedPath(can, hasFeature)` en `lib/permissions.ts`.

- [ ] **Step 1: Escribir las pruebas de tema y permisos**

`web/src/lib/colors.test.ts`:

```ts
import { describe, expect, test } from 'vitest';

import { applyBrandTheme, contrastRatio, normalizeHex, readableForeground } from './colors';

describe('colors', () => {
  test('normaliza colores hexadecimales de seis dígitos', () => {
    expect(normalizeHex('#AABBCC')).toBe('#aabbcc');
    expect(normalizeHex('aabbcc')).toBe('#aabbcc');
    expect(normalizeHex('#abc')).toBeNull();
  });

  test('calcula el contraste entre blanco y negro', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 0);
  });

  test('elige texto oscuro sobre un fondo claro', () => {
    expect(readableForeground('#facc15')).toBe('#0f172a');
    expect(readableForeground('#111827')).toBe('#ffffff');
  });

  test('aplica las variables de marca al documento', () => {
    applyBrandTheme({ primary_color: '#10b981', secondary_color: '#065f46' });
    const style = document.documentElement.style;
    expect(style.getPropertyValue('--brand-primary')).toBe('#10b981');
    expect(style.getPropertyValue('--brand-secondary')).toBe('#065f46');
    expect(style.getPropertyValue('--brand-fg')).toBe('#0f172a');
  });
});
```

`web/src/theme/ThemeProvider.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, test } from 'vitest';

import { ThemeProvider, useTheme } from './ThemeProvider';

function Probe() {
  const { mode, toggleMode } = useTheme();
  return <button onClick={toggleMode}>{mode}</button>;
}

describe('ThemeProvider', () => {
  test('usa el tema de la empresa cuando no hay preferencia', () => {
    render(
      <ThemeProvider companyMode="dark">
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByRole('button', { name: 'dark' })).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement).toHaveClass('dark');
  });

  test('la preferencia guardada manda sobre el tema de la empresa', () => {
    sessionStorage.setItem('agenda.web.theme', 'light');
    render(
      <ThemeProvider companyMode="dark">
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByRole('button', { name: 'light' })).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  test('alternar el tema persiste la preferencia', async () => {
    render(
      <ThemeProvider companyMode="light">
        <Probe />
      </ThemeProvider>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'light' }));
    expect(screen.getByRole('button', { name: 'dark' })).toBeInTheDocument();
    expect(sessionStorage.getItem('agenda.web.theme')).toBe('dark');
  });
});
```

`web/src/lib/permissions.test.ts`:

```ts
import { describe, expect, test } from 'vitest';

import { allows, firstAllowedPath, visibleNav } from './permissions';

describe('permisos', () => {
  test('la agenda acepta el permiso propio del trabajador', () => {
    expect(allows(['bookings.own.read'], 'bookings.read')).toBe(true);
    expect(allows(['bookings.own.write'], 'bookings.write')).toBe(true);
    expect(allows(['bookings.own.read'], 'bookings.write')).toBe(false);
  });

  test('oculta secciones sin permiso o sin funcionalidad', () => {
    const can = (permission: string) => permission !== 'reports.read';
    const hasFeature = (code: string) => code !== 'workforce';
    const paths = visibleNav(can, hasFeature).map((item) => item.path);
    expect(paths).toEqual(['/agenda', '/clientes', '/servicios', '/marca']);
  });

  test('sin secciones permitidas devuelve la pantalla de acceso restringido', () => {
    expect(firstAllowedPath(() => false, () => true)).toBe('/sin-acceso');
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

Run:

```bash
cd web
npm run test -- src/lib/colors.test.ts src/theme/ThemeProvider.test.tsx src/lib/permissions.test.ts
```

Expected: FAIL porque los módulos no existen.

- [ ] **Step 3: Implementar colores de marca**

`web/src/lib/colors.ts`:

```ts
export type Rgb = { r: number; g: number; b: number };

export function normalizeHex(value: string): string | null {
  const match = /^#?([0-9a-f]{6})$/i.exec(value.trim());
  return match ? `#${match[1].toLowerCase()}` : null;
}

export function hexToRgb(value: string): Rgb | null {
  const hex = normalizeHex(value);
  if (!hex) return null;
  return {
    r: Number.parseInt(hex.slice(1, 3), 16),
    g: Number.parseInt(hex.slice(3, 5), 16),
    b: Number.parseInt(hex.slice(5, 7), 16),
  };
}

function linearChannel(value: number): number {
  const normalized = value / 255;
  return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
}

export function relativeLuminance(value: string): number {
  const rgb = hexToRgb(value);
  if (!rgb) return 0;
  return 0.2126 * linearChannel(rgb.r) + 0.7152 * linearChannel(rgb.g) + 0.0722 * linearChannel(rgb.b);
}

export function contrastRatio(first: string, second: string): number {
  const a = relativeLuminance(first);
  const b = relativeLuminance(second);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

export function readableForeground(background: string): '#ffffff' | '#0f172a' {
  return contrastRatio(background, '#ffffff') >= contrastRatio(background, '#0f172a')
    ? '#ffffff'
    : '#0f172a';
}

export function applyBrandTheme(branding: { primary_color: string; secondary_color: string }): void {
  const primary = normalizeHex(branding.primary_color) ?? '#e50914';
  const secondary = normalizeHex(branding.secondary_color) ?? '#8b0000';
  const root = document.documentElement;
  root.style.setProperty('--brand-primary', primary);
  root.style.setProperty('--brand-secondary', secondary);
  root.style.setProperty('--brand-fg', readableForeground(primary));
}
```

- [ ] **Step 4: Implementar el ThemeProvider**

`web/src/theme/ThemeProvider.tsx`:

```tsx
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import type { ThemeMode } from '../api/types';

const STORAGE_KEY = 'agenda.web.theme';

type ThemeContextValue = {
  mode: ThemeMode;
  preference: ThemeMode | null;
  setMode(mode: ThemeMode): void;
  toggleMode(): void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readPreference(): ThemeMode | null {
  const value = sessionStorage.getItem(STORAGE_KEY);
  return value === 'light' || value === 'dark' ? value : null;
}

export function ThemeProvider({
  children,
  companyMode = 'light',
}: {
  children: ReactNode;
  companyMode?: ThemeMode;
}) {
  const [preference, setPreference] = useState<ThemeMode | null>(readPreference);
  const mode = preference ?? companyMode;

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = mode;
    root.classList.toggle('dark', mode === 'dark');
    root.style.colorScheme = mode;
  }, [mode]);

  const setMode = useCallback((next: ThemeMode) => {
    sessionStorage.setItem(STORAGE_KEY, next);
    setPreference(next);
  }, []);

  const toggleMode = useCallback(() => {
    setMode(mode === 'dark' ? 'light' : 'dark');
  }, [mode, setMode]);

  const value = useMemo<ThemeContextValue>(
    () => ({ mode, preference, setMode, toggleMode }),
    [mode, preference, setMode, toggleMode],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext);
  if (!value) throw new Error('useTheme debe usarse dentro de ThemeProvider.');
  return value;
}
```

- [ ] **Step 5: Completar la navegación por permisos**

`web/src/lib/permissions.ts`:

```ts
export function allows(permissions: string[], required: string): boolean {
  if (required === 'bookings.read') {
    return permissions.includes('bookings.read') || permissions.includes('bookings.own.read');
  }
  if (required === 'bookings.write') {
    return permissions.includes('bookings.write') || permissions.includes('bookings.own.write');
  }
  return permissions.includes(required);
}

export type CanFn = (permission: string) => boolean;
export type FeatureFn = (code: string) => boolean;

export type NavItem = {
  path: string;
  label: string;
  permission: string;
  feature?: string;
};

export const NAV_ITEMS: NavItem[] = [
  { path: '/agenda', label: 'Agenda', permission: 'bookings.read', feature: 'bookings' },
  { path: '/clientes', label: 'Clientes', permission: 'customers.read', feature: 'customers' },
  { path: '/servicios', label: 'Servicios', permission: 'catalog.read', feature: 'catalog' },
  { path: '/equipo', label: 'Equipo', permission: 'workforce.read', feature: 'workforce' },
  { path: '/resumen', label: 'Resumen', permission: 'reports.read', feature: 'reports' },
  { path: '/marca', label: 'Marca', permission: 'company.manage' },
];

export function visibleNav(can: CanFn, hasFeature: FeatureFn, items: NavItem[] = NAV_ITEMS): NavItem[] {
  return items.filter(
    (item) => can(item.permission) && (item.feature === undefined || hasFeature(item.feature)),
  );
}

export function firstAllowedPath(can: CanFn, hasFeature: FeatureFn): string {
  return visibleNav(can, hasFeature)[0]?.path ?? '/sin-acceso';
}
```

- [ ] **Step 6: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test -- src/lib/colors.test.ts src/theme/ThemeProvider.test.tsx src/lib/permissions.test.ts
```

Expected: 10 tests PASS.

- [ ] **Step 7: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/lib web/src/theme
git commit -m "feat(web): add brand theme provider and permission-aware navigation"
```

---

### Task 6: Acceso y selección de empresa

**Files:**
- Create: `web/src/features/auth/LoginPage.tsx`, `web/src/features/auth/LoginPage.test.tsx`, `web/src/features/companies/CompanyChooserPage.tsx`, `web/src/features/companies/CompanyChooserPage.test.tsx`
- Modify: `web/src/test/factories.ts`

**Interfaces:**
- Consumes: `useAuth`, `AuthContext`, `ApiError`, `Button`, `Field`, `Input`, `ErrorBanner`, `firstAllowedPath`, `allows`.
- Produces:
  - `LoginPage` y `CompanyChooserPage`.
  - `makeAuthValue(overrides?)` en `test/factories.ts`, un `AuthContextValue` completo para pruebas de pantallas.

- [ ] **Step 1: Agregar el valor de autenticación para pruebas**

Añadir a `web/src/test/factories.ts`:

```ts
import { vi } from 'vitest';

import type { AuthContextValue } from '../auth/AuthProvider';
import { allows } from '../lib/permissions';

export function makeAuthValue(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  const bootstrap = overrides.bootstrap ?? makeBootstrap();
  return {
    status: 'ready',
    user: bootstrap.user,
    companies: bootstrap.companies,
    company: bootstrap.company,
    bootstrap,
    permissions: bootstrap.permissions,
    error: null,
    login: vi.fn(async () => {}),
    selectCompany: vi.fn(async () => {}),
    logout: vi.fn(async () => {}),
    refreshBootstrap: vi.fn(async () => {}),
    can: (required) => allows(bootstrap.permissions, required),
    hasFeature: (code) => bootstrap.features[code] ?? false,
    ...overrides,
  };
}
```

- [ ] **Step 2: Escribir las pruebas de acceso y selección**

`web/src/features/auth/LoginPage.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, test, vi } from 'vitest';

import { ApiError } from '../../api/client';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { LoginPage } from './LoginPage';

function renderLogin(auth = makeAuthValue({ status: 'anonymous' })) {
  render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/agenda" element={<p>Agenda cargada</p>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
  return auth;
}

describe('LoginPage', () => {
  test('valida correo y contraseña antes de enviar', async () => {
    const auth = renderLogin();
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(screen.getByText('Ingresa tu correo.')).toBeInTheDocument();
    expect(screen.getByText('Ingresa tu contraseña.')).toBeInTheDocument();
    expect(auth.login).not.toHaveBeenCalled();
  });

  test('envía las credenciales y muestra el error del servidor', async () => {
    const login = vi.fn().mockRejectedValue(new ApiError(401, 'Credenciales inválidas.'));
    renderLogin(makeAuthValue({ status: 'anonymous', login }));

    await userEvent.type(screen.getByLabelText('Correo'), 'owner@agenda.app');
    await userEvent.type(screen.getByLabelText('Contraseña'), 'Secreta2026!');
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(login).toHaveBeenCalledWith('owner@agenda.app', 'Secreta2026!');
    expect(await screen.findByRole('alert')).toHaveTextContent('Credenciales inválidas.');
  });

  test('con sesión lista redirige a la primera sección permitida', async () => {
    const auth = makeAuthValue({ status: 'ready' });
    renderLogin(auth);
    expect(await screen.findByText('Agenda cargada')).toBeInTheDocument();
  });
});
```

`web/src/features/companies/CompanyChooserPage.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, test, vi } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue, makeCompany } from '../../test/factories';
import { CompanyChooserPage } from './CompanyChooserPage';

describe('CompanyChooserPage', () => {
  test('muestra las empresas y activa la elegida', async () => {
    const selectCompany = vi.fn().mockResolvedValue(undefined);
    const auth = makeAuthValue({
      status: 'choosingCompany',
      companies: [
        makeCompany({ id: 'company-a', display_name: 'Estudio Aurora' }),
        makeCompany({ id: 'company-b', display_name: 'Marca Demo Visual' }),
      ],
      selectCompany,
    });

    render(
      <AuthContext.Provider value={auth}>
        <MemoryRouter initialEntries={['/empresa']}>
          <Routes>
            <Route path="/empresa" element={<CompanyChooserPage />} />
            <Route path="/agenda" element={<p>Agenda cargada</p>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>,
    );

    await userEvent.click(screen.getByRole('button', { name: /Marca Demo Visual/ }));

    expect(selectCompany).toHaveBeenCalledWith(expect.objectContaining({ id: 'company-b' }));
    expect(await screen.findByText('Agenda cargada')).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Ejecutar las pruebas y ver el fallo**

Run:

```bash
cd web
npm run test -- src/features/auth/LoginPage.test.tsx src/features/companies/CompanyChooserPage.test.tsx
```

Expected: FAIL porque las pantallas no existen.

- [ ] **Step 4: Implementar la pantalla de acceso**

`web/src/features/auth/LoginPage.tsx`:

```tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useLocation, useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input } from '../../components/ui/Field';
import { firstAllowedPath } from '../../lib/permissions';

const schema = z.object({
  email: z.string().min(1, 'Ingresa tu correo.').email('Ingresa un correo válido.'),
  password: z.string().min(1, 'Ingresa tu contraseña.'),
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const { status, login, can, hasFeature } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  });

  useEffect(() => {
    if (status === 'ready') {
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? firstAllowedPath(can, hasFeature), { replace: true });
    }
    if (status === 'choosingCompany') navigate('/empresa', { replace: true });
  }, [can, hasFeature, location.state, navigate, status]);

  async function onSubmit(values: FormValues) {
    setSubmitError(null);
    try {
      await login(values.email, values.password);
    } catch (error) {
      setSubmitError(error instanceof ApiError ? error.message : 'No se pudo iniciar sesión.');
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface p-6">
      <section className="w-full max-w-sm rounded-xl border border-line bg-panel p-8 shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-wide text-brand">AGENDA</p>
        <h1 className="mt-1 text-2xl font-semibold text-ink">Panel del operador</h1>
        <p className="mt-1 text-sm text-muted">Accede con tu cuenta de la empresa.</p>

        <form className="mt-6 space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          {submitError ? <ErrorBanner message={submitError} /> : null}
          <Field label="Correo" htmlFor="login-email" error={errors.email?.message}>
            <Input
              id="login-email"
              type="email"
              autoComplete="email"
              {...register('email')}
            />
          </Field>
          <Field label="Contraseña" htmlFor="login-password" error={errors.password?.message}>
            <Input
              id="login-password"
              type="password"
              autoComplete="current-password"
              {...register('password')}
            />
          </Field>
          <Button type="submit" loading={isSubmitting} loadingLabel="Entrando…" className="w-full">
            Entrar
          </Button>
        </form>
      </section>
    </main>
  );
}
```

- [ ] **Step 5: Implementar el selector de empresa**

`web/src/features/companies/CompanyChooserPage.tsx`:

```tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { CompanySummary } from '../../api/types';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { ErrorBanner } from '../../components/ui/ErrorBanner';

export function CompanyChooserPage() {
  const { companies, selectCompany, logout, error } = useAuth();
  const navigate = useNavigate();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  async function choose(company: CompanySummary) {
    setPendingId(company.id);
    setLocalError(null);
    try {
      await selectCompany(company);
      navigate('/agenda', { replace: true });
    } catch {
      setLocalError('No se pudo activar la empresa. Intenta nuevamente.');
    } finally {
      setPendingId(null);
    }
  }

  return (
    <main className="min-h-screen bg-surface p-6">
      <div className="mx-auto max-w-3xl">
        <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-brand">AGENDA</p>
            <h1 className="text-2xl font-semibold text-ink">Elige una empresa</h1>
            <p className="mt-1 text-sm text-muted">Solo verás los datos de la empresa activa.</p>
          </div>
          <Button variant="ghost" onClick={() => void logout()}>
            Cerrar sesión
          </Button>
        </header>

        {error || localError ? <ErrorBanner message={localError ?? error ?? ''} /> : null}

        <ul className="mt-6 grid gap-3 sm:grid-cols-2">
          {companies.map((company) => (
            <li key={company.id}>
              <button
                type="button"
                onClick={() => void choose(company)}
                disabled={pendingId !== null}
                className="flex w-full items-center gap-4 rounded-lg border border-line bg-panel p-4 text-left transition hover:border-brand focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-60"
              >
                {company.logo_url ? (
                  <img src={company.logo_url} alt="" className="h-12 w-12 rounded-md object-contain" />
                ) : (
                  <span
                    aria-hidden="true"
                    className="flex h-12 w-12 items-center justify-center rounded-md bg-brand-soft text-lg font-semibold text-brand"
                  >
                    {(company.display_name || company.name).slice(0, 1)}
                  </span>
                )}
                <span>
                  <span className="block font-medium text-ink">{company.display_name || company.name}</span>
                  <span className="block text-sm text-muted">{company.slug}</span>
                </span>
                <span className="ml-auto text-sm text-brand">
                  {pendingId === company.id ? 'Activando…' : 'Entrar'}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
```

- [ ] **Step 6: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test -- src/features/auth/LoginPage.test.tsx src/features/companies/CompanyChooserPage.test.tsx
```

Expected: 4 tests PASS.

- [ ] **Step 7: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/features/auth web/src/features/companies web/src/test/factories.ts
git commit -m "feat(web): add login and company chooser screens"
```

---

### Task 7: Providers, router, guards y layout

**Files:**
- Create: `web/src/app/queryClient.ts`, `web/src/app/providers.tsx`, `web/src/app/guards.tsx`, `web/src/app/HomeRedirect.tsx`, `web/src/app/AppLayout.tsx`, `web/src/app/PlaceholderPage.tsx`, `web/src/app/router.tsx`, `web/src/app/AppLayout.test.tsx`, `web/src/app/guards.test.tsx`, `web/src/lib/useDebouncedValue.ts`, `web/src/lib/useDebouncedValue.test.ts`, `web/src/lib/useOnlineStatus.ts`, `web/src/lib/useOnlineStatus.test.ts`
- Modify: `web/src/main.tsx`
- Delete: `web/src/App.tsx`, `web/src/App.test.tsx`

**Interfaces:**
- Consumes: `AuthProvider`, `ThemeProvider`, `visibleNav`, `firstAllowedPath`, UI primitives, `LoginPage`, `CompanyChooserPage`.
- Produces:
  - `createQueryClient()`, `AppProviders({ children?, gateway?, store?, runtime?, queryClient? })`.
  - `RequireAuthenticated`, `RequireReady`, `RequirePermission`, `HomeRedirect`, `AccessDeniedPage`, `NotFoundPage`.
  - `AppLayout`, `routeObjects: RouteObject[]`, `router`.
  - `useDebouncedValue<T>(value, delay?)` y `useOnlineStatus()`.
  - `PlaceholderPage` temporal para las rutas que las tareas 10 a 19 reemplazan.

- [ ] **Step 1: Escribir las pruebas del layout y los guards**

`web/src/lib/useDebouncedValue.test.ts`:

```ts
import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

import { useDebouncedValue } from './useDebouncedValue';

describe('useDebouncedValue', () => {
  afterEach(() => vi.useRealTimers());

  test('retrasa la propagación del valor', () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ value }: { value: string }) => useDebouncedValue(value, 300),
      { initialProps: { value: 'a' } },
    );

    rerender({ value: 'ab' });
    expect(result.current).toBe('a');

    act(() => vi.advanceTimersByTime(300));
    expect(result.current).toBe('ab');
  });
});
```

`web/src/lib/useOnlineStatus.test.ts`:

```ts
import { act, renderHook } from '@testing-library/react';
import { describe, expect, test } from 'vitest';

import { useOnlineStatus } from './useOnlineStatus';

describe('useOnlineStatus', () => {
  test('reacciona a los eventos del navegador', () => {
    const { result } = renderHook(() => useOnlineStatus());
    expect(result.current).toBe(true);

    act(() => window.dispatchEvent(new Event('offline')));
    expect(result.current).toBe(false);

    act(() => window.dispatchEvent(new Event('online')));
    expect(result.current).toBe(true);
  });
});
```

`web/src/app/guards.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, test } from 'vitest';

import { AuthContext } from '../auth/AuthProvider';
import { makeAuthValue } from '../test/factories';
import { RequireAuthenticated, RequirePermission, RequireReady } from './guards';

function renderGuarded(auth = makeAuthValue(), initial = '/agenda') {
  render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route
            path="/agenda"
            element={
              <RequireAuthenticated>
                <RequireReady>
                  <RequirePermission permission="bookings.read">
                    <p>Contenido privado</p>
                  </RequirePermission>
                </RequireReady>
              </RequireAuthenticated>
            }
          />
          <Route path="/login" element={<p>Pantalla de acceso</p>} />
          <Route path="/empresa" element={<p>Selector de empresa</p>} />
          <Route path="/sin-acceso" element={<p>Acceso restringido</p>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe('guards', () => {
  test('sin sesión redirige al acceso', () => {
    renderGuarded(makeAuthValue({ status: 'anonymous' }));
    expect(screen.getByText('Pantalla de acceso')).toBeInTheDocument();
  });

  test('una sesión sin empresa redirige al selector', () => {
    renderGuarded(makeAuthValue({ status: 'choosingCompany' }));
    expect(screen.getByText('Selector de empresa')).toBeInTheDocument();
  });

  test('sin permiso muestra acceso restringido', () => {
    renderGuarded(makeAuthValue({ can: () => false }));
    expect(screen.getByText('Acceso restringido')).toBeInTheDocument();
  });

  test('con permiso renderiza el contenido', () => {
    renderGuarded();
    expect(screen.getByText('Contenido privado')).toBeInTheDocument();
  });
});
```

`web/src/app/AppLayout.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, test, vi } from 'vitest';

import { AuthContext } from '../auth/AuthProvider';
import { ThemeProvider } from '../theme/ThemeProvider';
import { makeAuthValue, makeCompany } from '../test/factories';
import { AppLayout } from './AppLayout';

function renderLayout(auth = makeAuthValue()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={auth}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider companyMode="light">
          <MemoryRouter initialEntries={['/agenda']}>
            <Routes>
              <Route element={<AppLayout />}>
                <Route path="/agenda" element={<p>Contenido de agenda</p>} />
              </Route>
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
  return { auth, queryClient };
}

describe('AppLayout', () => {
  test('muestra solo las secciones permitidas y el usuario', () => {
    renderLayout(makeAuthValue({ can: (permission) => permission !== 'reports.read' }));
    expect(screen.getByRole('link', { name: 'Agenda' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Resumen' })).not.toBeInTheDocument();
    expect(screen.getByText('owner@agenda.app')).toBeInTheDocument();
    expect(screen.getByText('Contenido de agenda')).toBeInTheDocument();
  });

  test('permite cambiar de empresa', async () => {
    const selectCompany = vi.fn().mockResolvedValue(undefined);
    const auth = makeAuthValue({
      companies: [
        makeCompany({ id: 'company-a', display_name: 'Estudio Aurora' }),
        makeCompany({ id: 'company-b', display_name: 'Marca Demo Visual' }),
      ],
      selectCompany,
    });
    renderLayout(auth);

    await userEvent.selectOptions(screen.getByLabelText('Empresa'), 'company-b');

    expect(selectCompany).toHaveBeenCalledWith(expect.objectContaining({ id: 'company-b' }));
  });

  test('alterna el tema y cierra la sesión', async () => {
    const logout = vi.fn().mockResolvedValue(undefined);
    renderLayout(makeAuthValue({ logout }));

    await userEvent.click(screen.getByRole('button', { name: 'Tema oscuro' }));
    expect(sessionStorage.getItem('agenda.web.theme')).toBe('dark');

    await userEvent.click(screen.getByRole('button', { name: 'Salir' }));
    expect(logout).toHaveBeenCalledTimes(1);
  });

  test('el botón actualizar recarga bootstrap e invalida consultas', async () => {
    const refreshBootstrap = vi.fn().mockResolvedValue(undefined);
    const { queryClient } = renderLayout(makeAuthValue({ refreshBootstrap }));
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');

    await userEvent.click(screen.getByRole('button', { name: 'Actualizar' }));

    expect(refreshBootstrap).toHaveBeenCalledTimes(1);
    expect(invalidate).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

Run:

```bash
cd web
npm run test -- src/app src/lib/useDebouncedValue.test.ts src/lib/useOnlineStatus.test.ts
```

Expected: FAIL porque los módulos no existen.

- [ ] **Step 3: Implementar los hooks compartidos**

`web/src/lib/useDebouncedValue.ts`:

```ts
import { useEffect, useState } from 'react';

export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [delay, value]);

  return debounced;
}
```

`web/src/lib/useOnlineStatus.ts`:

```ts
import { useEffect, useState } from 'react';

export function useOnlineStatus(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine);

  useEffect(() => {
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);

  return online;
}
```

- [ ] **Step 4: Implementar guards y redirecciones**

`web/src/app/guards.tsx`:

```tsx
import type { ReactNode } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/AuthProvider';
import { Skeleton } from '../components/ui/Skeleton';
import { firstAllowedPath } from '../lib/permissions';

function FullPageLoading() {
  return (
    <main className="p-8">
      <Skeleton rows={6} />
    </main>
  );
}

export function RequireAuthenticated({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === 'loading') return <FullPageLoading />;
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

export function RequireReady({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  if (status === 'choosingCompany') return <Navigate to="/empresa" replace />;
  if (status !== 'ready') return <FullPageLoading />;
  return <>{children}</>;
}

export function RequirePermission({
  permission,
  children,
}: {
  permission: string;
  children: ReactNode;
}) {
  const { can } = useAuth();
  if (!can(permission)) return <Navigate to="/sin-acceso" replace />;
  return <>{children}</>;
}

export function AccessDeniedPage() {
  const { can, hasFeature } = useAuth();
  const target = firstAllowedPath(can, hasFeature);
  return (
    <section className="mx-auto max-w-lg rounded-lg border border-line bg-panel p-8 text-center">
      <h1 className="text-xl font-semibold text-ink">Acceso restringido</h1>
      <p className="mt-2 text-sm text-muted">
        No tienes permiso para esta sección con tu rol actual.
      </p>
      {target !== '/sin-acceso' ? (
        <Link className="mt-4 inline-block text-sm font-medium text-brand underline" to={target}>
          Ir a una sección disponible
        </Link>
      ) : null}
    </section>
  );
}

export function NotFoundPage() {
  return (
    <section className="mx-auto max-w-lg rounded-lg border border-line bg-panel p-8 text-center">
      <h1 className="text-xl font-semibold text-ink">Página no encontrada</h1>
      <p className="mt-2 text-sm text-muted">La ruta solicitada no existe en el panel.</p>
    </section>
  );
}
```

`web/src/app/HomeRedirect.tsx`:

```tsx
import { Navigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthProvider';
import { firstAllowedPath } from '../lib/permissions';

export function HomeRedirect() {
  const { status, can, hasFeature } = useAuth();
  if (status === 'anonymous') return <Navigate to="/login" replace />;
  if (status === 'choosingCompany') return <Navigate to="/empresa" replace />;
  if (status !== 'ready') return null;
  return <Navigate to={firstAllowedPath(can, hasFeature)} replace />;
}
```

- [ ] **Step 5: Implementar layout, providers y router**

`web/src/app/queryClient.ts`:

```ts
import { QueryClient } from '@tanstack/react-query';

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        refetchOnWindowFocus: false,
        staleTime: 30_000,
      },
    },
  });
}
```

`web/src/app/AppLayout.tsx`:

```tsx
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthProvider';
import { Button } from '../components/ui/Button';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { visibleNav } from '../lib/permissions';
import { useOnlineStatus } from '../lib/useOnlineStatus';
import { useTheme } from '../theme/ThemeProvider';

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `block whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition ${
    isActive ? 'bg-brand-soft text-brand' : 'text-ink hover:bg-surface'
  }`;

export function AppLayout() {
  const {
    company,
    companies,
    user,
    can,
    hasFeature,
    bootstrap,
    logout,
    selectCompany,
    refreshBootstrap,
  } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const online = useOnlineStatus();
  const { mode, toggleMode } = useTheme();
  const [refreshing, setRefreshing] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [layoutError, setLayoutError] = useState<string | null>(null);
  const nav = visibleNav(can, hasFeature);

  async function reload() {
    setRefreshing(true);
    setLayoutError(null);
    try {
      await refreshBootstrap();
      await queryClient.invalidateQueries();
    } catch (error) {
      setLayoutError(error instanceof ApiError ? error.message : 'No se pudo actualizar el panel.');
    } finally {
      setRefreshing(false);
    }
  }

  async function switchCompany(companyId: string) {
    const target = companies.find((item) => item.id === companyId);
    if (!target) return;
    setSwitching(true);
    setLayoutError(null);
    try {
      await selectCompany(target);
      navigate('/agenda', { replace: true });
    } catch (error) {
      setLayoutError(
        error instanceof ApiError ? error.message : 'No se pudo cambiar de empresa.',
      );
    } finally {
      setSwitching(false);
    }
  }

  async function signOut() {
    await logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="min-h-screen bg-surface md:flex">
      <aside className="border-b border-line bg-panel md:flex md:w-56 md:shrink-0 md:flex-col md:border-b-0 md:border-r">
        <div className="border-b border-line px-4 py-4 md:py-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">AGENDA</p>
          {company?.logo_url ? (
            <img src={company.logo_url} alt="" className="mt-2 h-8 max-w-[10rem] object-contain" />
          ) : null}
          <p className="mt-1 truncate text-base font-semibold text-ink">
            {company?.display_name || company?.name}
          </p>
        </div>
        <nav aria-label="Secciones" className="flex gap-1 overflow-x-auto p-3 md:flex-1 md:flex-col md:space-y-1">
          {nav.map((item) => (
            <NavLink key={item.path} to={item.path} className={linkClass}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-line px-3 py-2 text-xs text-muted">
          <p className="truncate" title={user?.email}>
            {user?.email}
          </p>
          <p>{bootstrap?.membership.role_display}</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-line bg-panel px-4 py-3">
          <div className="flex flex-wrap items-center gap-3">
            <p className="font-semibold text-ink md:hidden">AGENDA</p>
            {companies.length > 1 ? (
              <label htmlFor="company-switcher" className="flex items-center gap-2 text-sm text-muted">
                Empresa
                <select
                  id="company-switcher"
                  value={company?.id ?? ''}
                  disabled={switching}
                  onChange={(event) => void switchCompany(event.target.value)}
                  className="rounded-md border border-line bg-panel px-2 py-1 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
                >
                  {companies.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.display_name || item.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <div className="ml-auto flex flex-wrap items-center gap-2">
              <Button
                variant="secondary"
                onClick={() => void reload()}
                loading={refreshing}
                loadingLabel="Actualizando…"
              >
                Actualizar
              </Button>
              <Button variant="ghost" onClick={toggleMode}>
                {mode === 'dark' ? 'Tema claro' : 'Tema oscuro'}
              </Button>
              <Button variant="ghost" onClick={() => void signOut()}>
                Salir
              </Button>
            </div>
          </div>

          {!online ? (
            <div className="mt-3">
              <ErrorBanner
                message="Sin conexión con el servidor."
                onRetry={() => void queryClient.refetchQueries({ type: 'active' })}
              />
            </div>
          ) : null}
          {layoutError ? (
            <div className="mt-3">
              <ErrorBanner message={layoutError} />
            </div>
          ) : null}
        </header>

        <main className="min-w-0 flex-1 p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

`web/src/app/PlaceholderPage.tsx`:

```tsx
export function PlaceholderPage({ title }: { title: string }) {
  return (
    <section>
      <h1 className="text-2xl font-semibold text-ink">{title}</h1>
      <p className="mt-1 text-sm text-muted">Este módulo se habilita en la siguiente tarea del plan.</p>
    </section>
  );
}
```

`web/src/app/providers.tsx`:

```tsx
import { QueryClientProvider, type QueryClient } from '@tanstack/react-query';
import { useEffect, useState, type ReactNode } from 'react';
import { RouterProvider } from 'react-router-dom';

import { authGateway, sessionRuntime } from '../api/runtime';
import {
  AuthProvider,
  useAuth,
  type AuthGateway,
} from '../auth/AuthProvider';
import { localSessionStore, type SessionStore } from '../auth/sessionStore';
import { applyBrandTheme } from '../lib/colors';
import { ThemeProvider } from '../theme/ThemeProvider';
import { createQueryClient } from './queryClient';
import { router } from './router';

type Runtime = { accessToken: string | null; tenantContextId: string | null };

function ThemeHost({ children }: { children: ReactNode }) {
  const { company } = useAuth();
  return (
    <ThemeProvider companyMode={company?.theme_mode ?? 'light'}>{children}</ThemeProvider>
  );
}

function BrandThemeSync() {
  const { company } = useAuth();
  useEffect(() => {
    if (company) applyBrandTheme(company);
  }, [company]);
  return null;
}

export function AppProviders({
  children,
  gateway = authGateway,
  store = localSessionStore,
  runtime = sessionRuntime,
  queryClient,
}: {
  children?: ReactNode;
  gateway?: AuthGateway;
  store?: SessionStore;
  runtime?: Runtime;
  queryClient?: QueryClient;
}) {
  const [fallbackClient] = useState(createQueryClient);
  const client = queryClient ?? fallbackClient;

  return (
    <QueryClientProvider client={client}>
      <AuthProvider gateway={gateway} store={store} runtime={runtime}>
        <ThemeHost>
          <BrandThemeSync />
          {children ?? <RouterProvider router={router} />}
        </ThemeHost>
      </AuthProvider>
    </QueryClientProvider>
  );
}
```

`web/src/app/router.tsx`:

```tsx
import { createBrowserRouter, type RouteObject } from 'react-router-dom';

import { CompanyChooserPage } from '../features/companies/CompanyChooserPage';
import { LoginPage } from '../features/auth/LoginPage';
import { AppLayout } from './AppLayout';
import {
  AccessDeniedPage,
  NotFoundPage,
  RequireAuthenticated,
  RequirePermission,
  RequireReady,
} from './guards';
import { HomeRedirect } from './HomeRedirect';
import { PlaceholderPage } from './PlaceholderPage';

export const routeObjects: RouteObject[] = [
  { path: '/login', element: <LoginPage /> },
  {
    path: '/empresa',
    element: (
      <RequireAuthenticated>
        <CompanyChooserPage />
      </RequireAuthenticated>
    ),
  },
  {
    path: '/',
    element: (
      <RequireAuthenticated>
        <RequireReady>
          <AppLayout />
        </RequireReady>
      </RequireAuthenticated>
    ),
    children: [
      { index: true, element: <HomeRedirect /> },
      {
        path: 'agenda',
        element: (
          <RequirePermission permission="bookings.read">
            <PlaceholderPage title="Agenda" />
          </RequirePermission>
        ),
      },
      {
        path: 'clientes',
        element: (
          <RequirePermission permission="customers.read">
            <PlaceholderPage title="Clientes" />
          </RequirePermission>
        ),
      },
      {
        path: 'servicios',
        element: (
          <RequirePermission permission="catalog.read">
            <PlaceholderPage title="Servicios" />
          </RequirePermission>
        ),
      },
      {
        path: 'equipo',
        element: (
          <RequirePermission permission="workforce.read">
            <PlaceholderPage title="Equipo" />
          </RequirePermission>
        ),
      },
      {
        path: 'resumen',
        element: (
          <RequirePermission permission="reports.read">
            <PlaceholderPage title="Resumen" />
          </RequirePermission>
        ),
      },
      {
        path: 'marca',
        element: (
          <RequirePermission permission="company.manage">
            <PlaceholderPage title="Marca" />
          </RequirePermission>
        ),
      },
      { path: 'sin-acceso', element: <AccessDeniedPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routeObjects);
```

`web/src/main.tsx` (reemplaza el contenido de la tarea 1):

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';

import { AppProviders } from './app/providers';
import { router } from './app/router';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
);
```

Borrar `web/src/App.tsx` y `web/src/App.test.tsx` (el smoke test inicial deja de aplicar).

- [ ] **Step 6: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test
```

Expected: todas las pruebas PASS, incluidas las 4 de guards y las 4 de layout.

- [ ] **Step 7: Verificar tipos, lint y build**

Run:

```bash
cd web
npm run build
npm run lint
```

Expected: sin errores. `npm run build` genera `dist/`.

- [ ] **Step 8: Validación visual del shell (claro y oscuro)**

Con el backend local en `8000`, ejecutar `npm run dev`, iniciar sesión y revisar en 1280 px y 768 px:

- Navegación lateral visible desde 768 px, sin desbordes horizontales.
- Encabezado con empresa, usuario, actualizar, tema y salir.
- Alternar tema conserva la pantalla y cambia todos los tokens.
- Foco visible al recorrer con Tab y menú de empresa operable con teclado.

- [ ] **Step 9: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/app web/src/lib web/src/main.tsx web/src/App.tsx web/src/App.test.tsx
git commit -m "feat(web): add app shell with guards, providers and responsive layout"
```

---

### Task 8: Módulos de API por dominio y claves de consulta

**Files:**
- Create: `web/src/api/agenda.ts`, `web/src/api/customers.ts`, `web/src/api/services.ts`, `web/src/api/team.ts`, `web/src/api/summary.ts`, `web/src/api/branding.ts`, `web/src/api/queryKeys.ts`, `web/src/api/domain.test.ts`
- Modify: `web/src/api/runtime.ts`

**Interfaces:**
- Consumes: `ApiClient`, `Paginated`, tipos base y `UUID`.
- Produces:
  - `createAgendaApi`, `createCustomersApi`, `createServicesApi`, `createTeamApi`, `createSummaryApi`, `createBrandingApi` y sus tipos `AgendaApi`, etc.
  - `agendaApi`, `customersApi`, `servicesApi`, `teamApi`, `summaryApi`, `brandingApi` en `runtime.ts`.
  - `queryKeys` con la empresa activa como segundo elemento de cada clave.

- [ ] **Step 1: Escribir las pruebas de los módulos de dominio**

`web/src/api/domain.test.ts`:

```ts
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import { server } from '../test/server';
import { createAgendaApi } from './agenda';
import { createBrandingApi } from './branding';
import { ApiClient } from './client';
import { createCustomersApi } from './customers';
import { createServicesApi } from './services';
import { createSummaryApi } from './summary';
import { createTeamApi } from './team';

function makeClient() {
  return new ApiClient({
    baseUrl: 'http://api.test',
    getAccessToken: () => 'access-1',
    getTenantContextId: () => 'ctx-1',
  });
}

const bookingFixture = {
  id: 'booking-1',
  company: 'company-a',
  branch: 'branch-1',
  branch_name: 'Providencia',
  customer: 'customer-1',
  customer_name: 'Ana Díaz',
  customer_email: 'ana@example.com',
  service: 'service-1',
  service_name: 'Corte',
  worker: 'worker-1',
  worker_name: 'Paula Rojas',
  start_at: '2026-11-12T13:00:00Z',
  end_at: '2026-11-12T13:30:00Z',
  duration_minutes: 30,
  price: '12000.00',
  status: 'scheduled',
  status_display: 'Agendada',
  source: 'staff',
  source_display: 'Equipo',
  notes: '',
  public_code: 'ABCDEFGHIJ',
  canceled_at: null,
  canceled_reason: '',
  created_at: '2026-11-11T12:00:00Z',
  updated_at: '2026-11-11T12:00:00Z',
};

describe('agendaApi', () => {
  test('crea la reserva con el inicio en UTC y consulta disponibilidad', async () => {
    let createBody: unknown;
    let availabilityUrl = '';
    server.use(
      http.get('http://api.test/api/v1/bookings/availability/', ({ request }) => {
        availabilityUrl = request.url;
        return HttpResponse.json({
          date: '2026-11-12',
          timezone: 'America/Santiago',
          slots: [{ start_at: '2026-11-12T13:00:00Z', end_at: '2026-11-12T13:30:00Z', label: '10:00' }],
        });
      }),
      http.post('http://api.test/api/v1/bookings/', async ({ request }) => {
        createBody = await request.json();
        return HttpResponse.json(bookingFixture, { status: 201 });
      }),
    );

    const api = createAgendaApi(makeClient());
    const availability = await api.availability({
      branch: 'branch-1',
      service: 'service-1',
      worker: 'worker-1',
      date: '2026-11-12',
    });
    const booking = await api.createBooking({
      branch: 'branch-1',
      customer: 'customer-1',
      service: 'service-1',
      worker: 'worker-1',
      start_at: availability.slots[0].start_at,
      notes: 'Primera visita',
    });

    expect(availabilityUrl).toContain('date=2026-11-12');
    expect(createBody).toMatchObject({
      branch: 'branch-1',
      customer: 'customer-1',
      service: 'service-1',
      worker: 'worker-1',
      start_at: '2026-11-12T13:00:00Z',
      notes: 'Primera visita',
    });
    expect(booking.id).toBe('booking-1');
  });

  test('usa la acción dedicada para reprogramar y cambiar de estado', async () => {
    const calls: string[] = [];
    server.use(
      http.post('http://api.test/api/v1/bookings/booking-1/reschedule/', () => {
        calls.push('reschedule');
        return HttpResponse.json({ ...bookingFixture, start_at: '2026-11-13T14:00:00Z' });
      }),
      http.post('http://api.test/api/v1/bookings/booking-1/confirm/', () => {
        calls.push('confirm');
        return HttpResponse.json({ ...bookingFixture, status: 'confirmed' });
      }),
      http.patch('http://api.test/api/v1/bookings/booking-1/', async ({ request }) => {
        calls.push('notes');
        expect(await request.json()).toEqual({ notes: 'Llegó antes' });
        return HttpResponse.json({ ...bookingFixture, notes: 'Llegó antes' });
      }),
    );

    const api = createAgendaApi(makeClient());
    await api.rescheduleBooking('booking-1', { start_at: '2026-11-13T14:00:00Z' });
    await api.transitionBooking('booking-1', 'confirm');
    await api.updateNotes('booking-1', 'Llegó antes');

    expect(calls).toEqual(['reschedule', 'confirm', 'notes']);
  });
});

describe('customersApi', () => {
  test('busca, crea y desactiva clientes', async () => {
    let listUrl = '';
    let created: unknown;
    let deactivated: unknown;
    server.use(
      http.get('http://api.test/api/v1/customers/', ({ request }) => {
        listUrl = request.url;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
      http.post('http://api.test/api/v1/customers/', async ({ request }) => {
        created = await request.json();
        return HttpResponse.json({ id: 'customer-2', ...(created as object) }, { status: 201 });
      }),
      http.patch('http://api.test/api/v1/customers/customer-2/', async ({ request }) => {
        deactivated = await request.json();
        return HttpResponse.json({ id: 'customer-2', active: false });
      }),
    );

    const api = createCustomersApi(makeClient());
    await api.list({ search: 'ana', active: true });
    await api.create({ first_name: 'Ana', email: 'ana@example.com' });
    await api.setActive('customer-2', false);

    expect(listUrl).toContain('search=ana');
    expect(listUrl).toContain('active=true');
    expect(created).toMatchObject({ first_name: 'Ana', email: 'ana@example.com' });
    expect(deactivated).toEqual({ active: false });
  });
});

describe('servicesApi', () => {
  test('envía duración, buffers y sucursales del servicio', async () => {
    let body: unknown;
    server.use(
      http.post('http://api.test/api/v1/services/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: 'service-1', ...(body as object) }, { status: 201 });
      }),
    );

    await createServicesApi(makeClient()).create({
      name: 'Corte',
      description: '',
      duration_minutes: 45,
      price: '12000.00',
      buffer_before_minutes: 5,
      buffer_after_minutes: 10,
      branches: ['branch-1'],
      active: true,
    });

    expect(body).toMatchObject({
      duration_minutes: 45,
      buffer_before_minutes: 5,
      buffer_after_minutes: 10,
      branches: ['branch-1'],
    });
  });
});

describe('teamApi', () => {
  test('crea horario, pausa, ausencia y bloqueo con sus campos', async () => {
    const bodies: Record<string, unknown> = {};
    server.use(
      http.post('http://api.test/api/v1/working-hours/', async ({ request }) => {
        bodies.hours = await request.json();
        return HttpResponse.json({ id: 'hours-1' }, { status: 201 });
      }),
      http.post('http://api.test/api/v1/breaks/', async ({ request }) => {
        bodies.break = await request.json();
        return HttpResponse.json({ id: 'break-1' }, { status: 201 });
      }),
      http.post('http://api.test/api/v1/time-off/', async ({ request }) => {
        bodies.timeOff = await request.json();
        return HttpResponse.json({ id: 'timeoff-1' }, { status: 201 });
      }),
      http.post('http://api.test/api/v1/blocked-slots/', async ({ request }) => {
        bodies.blocked = await request.json();
        return HttpResponse.json({ id: 'blocked-1' }, { status: 201 });
      }),
      http.delete('http://api.test/api/v1/working-hours/hours-1/', () => new HttpResponse(null, { status: 204 })),
    );

    const api = createTeamApi(makeClient());
    await api.workingHours.create({
      worker: 'worker-1',
      branch: 'branch-1',
      weekday: 0,
      start_time: '09:00',
      end_time: '13:00',
    });
    await api.breaks.create({
      worker: 'worker-1',
      branch: 'branch-1',
      weekday: 0,
      start_time: '11:00',
      end_time: '11:15',
      label: 'Pausa',
    });
    await api.timeOff.create({
      worker: 'worker-1',
      branch: 'branch-1',
      starts_at: '2026-11-20T13:00:00Z',
      ends_at: '2026-11-20T21:00:00Z',
      reason: 'Vacaciones',
    });
    await api.blockedSlots.create({
      worker: 'worker-1',
      branch: null,
      starts_at: '2026-11-21T13:00:00Z',
      ends_at: '2026-11-21T15:00:00Z',
      reason: 'Trámite',
    });
    await expect(api.workingHours.remove('hours-1')).resolves.toBeUndefined();

    expect(bodies.hours).toMatchObject({ weekday: 0, start_time: '09:00', end_time: '13:00' });
    expect(bodies.break).toMatchObject({ label: 'Pausa' });
    expect(bodies.timeOff).toMatchObject({ reason: 'Vacaciones' });
    expect(bodies.blocked).toMatchObject({ branch: null });
  });
});

describe('summaryApi', () => {
  test('envía rango y sucursal a ambos informes', async () => {
    const urls: string[] = [];
    server.use(
      http.get('http://api.test/api/v1/reports/sales-summary/', ({ request }) => {
        urls.push(request.url);
        return HttpResponse.json({ totals: {} });
      }),
      http.get('http://api.test/api/v1/reports/cash-summary/', ({ request }) => {
        urls.push(request.url);
        return HttpResponse.json({ totals: {} });
      }),
    );

    const api = createSummaryApi(makeClient());
    await api.sales({ date_from: '2026-11-05', date_to: '2026-11-11', branch: 'branch-1' });
    await api.cash({ date_from: '2026-11-05', date_to: '2026-11-11', branch: 'branch-1' });

    expect(urls).toHaveLength(2);
    urls.forEach((url) => {
      expect(url).toContain('date_from=2026-11-05');
      expect(url).toContain('date_to=2026-11-11');
      expect(url).toContain('branch=branch-1');
    });
  });
});

describe('brandingApi', () => {
  test('actualiza la marca y sube el logo como multipart', async () => {
    let patchBody: unknown;
    let logoFile: File | null = null;
    server.use(
      http.patch('http://api.test/api/v1/company/branding/', async ({ request }) => {
        patchBody = await request.json();
        return HttpResponse.json({ display_name: 'Aurora', slug: 'aurora' });
      }),
      http.post('http://api.test/api/v1/company/branding/logo/', async ({ request }) => {
        const form = await request.formData();
        logoFile = form.get('logo') as File;
        return HttpResponse.json({ display_name: 'Aurora', logo_url: '/media/logo.png' });
      }),
    );

    const api = createBrandingApi(makeClient());
    await api.update({ display_name: 'Aurora', theme_mode: 'dark' });
    const file = new File(['png'], 'logo.png', { type: 'image/png' });
    await api.uploadLogo(file);

    expect(patchBody).toEqual({ display_name: 'Aurora', theme_mode: 'dark' });
    expect(logoFile?.name).toBe('logo.png');
  });

  test('propaga el error por campo del servidor', async () => {
    server.use(
      http.patch('http://api.test/api/v1/company/branding/', () =>
        HttpResponse.json({ slug: ['Este identificador de empresa ya está ocupado.'] }, { status: 400 }),
      ),
    );

    await expect(
      createBrandingApi(makeClient()).update({ slug: 'ocupado' }),
    ).rejects.toMatchObject({
      status: 400,
      fields: { slug: ['Este identificador de empresa ya está ocupado.'] },
    });
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

Run: `cd web && npm run test -- src/api/domain.test.ts`

Expected: FAIL porque los módulos no existen.

- [ ] **Step 3: Implementar el módulo de agenda**

`web/src/api/agenda.ts`:

```ts
import type { ApiClient } from './client';
import type { ISODate, ISODateTime, Paginated, UUID } from './types';

export type BookingStatus = 'scheduled' | 'confirmed' | 'completed' | 'canceled' | 'no_show';

export type Booking = {
  id: UUID;
  company: UUID;
  branch: UUID;
  branch_name: string;
  customer: UUID;
  customer_name: string;
  customer_email: string;
  service: UUID;
  service_name: string;
  worker: UUID;
  worker_name: string;
  start_at: ISODateTime;
  end_at: ISODateTime;
  duration_minutes: number;
  price: string;
  status: BookingStatus;
  status_display: string;
  source: string;
  source_display: string;
  notes: string;
  public_code: string;
  canceled_at: ISODateTime | null;
  canceled_reason: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type BookingListParams = {
  branch?: UUID;
  worker?: UUID;
  service?: UUID;
  customer?: UUID;
  status?: BookingStatus;
  date?: ISODate;
  date_from?: ISODate;
  date_to?: ISODate;
  page?: number;
  ordering?: string;
};

export type BookingCreateInput = {
  branch: UUID;
  customer: UUID;
  service: UUID;
  worker: UUID;
  start_at: ISODateTime;
  notes?: string;
};

export type AvailabilityParams = {
  branch: UUID;
  service: UUID;
  worker: UUID;
  date: ISODate;
};

export type AvailabilitySlot = {
  start_at: ISODateTime;
  end_at: ISODateTime;
  label: string;
};

export type Availability = {
  date: ISODate;
  timezone: string;
  slots: AvailabilitySlot[];
};

export type RescheduleInput = {
  start_at: ISODateTime;
  worker?: UUID;
  reason?: string;
};

export type BookingAction = 'confirm' | 'cancel' | 'complete' | 'no-show';

export function createAgendaApi(client: ApiClient) {
  return {
    listBookings: (params: BookingListParams = {}) =>
      client.get<Paginated<Booking>>('/api/v1/bookings/', { ...params }),

    availability: (params: AvailabilityParams) =>
      client.get<Availability>('/api/v1/bookings/availability/', { ...params }),

    createBooking: (input: BookingCreateInput) =>
      client.post<Booking>('/api/v1/bookings/', input),

    rescheduleBooking: (id: UUID, input: RescheduleInput) =>
      client.post<Booking>(`/api/v1/bookings/${id}/reschedule/`, input),

    transitionBooking: (id: UUID, action: BookingAction, reason = '') =>
      client.post<Booking>(`/api/v1/bookings/${id}/${action}/`, reason ? { reason } : {}),

    updateNotes: (id: UUID, notes: string) =>
      client.patch<Booking>(`/api/v1/bookings/${id}/`, { notes }),
  };
}

export type AgendaApi = ReturnType<typeof createAgendaApi>;
```

- [ ] **Step 4: Implementar clientes, servicios y equipo**

`web/src/api/customers.ts`:

```ts
import type { ApiClient } from './client';
import type { ISODateTime, Paginated, UUID } from './types';

export type Customer = {
  id: UUID;
  company: UUID;
  first_name: string;
  last_name: string;
  display_name: string;
  email: string;
  phone: string;
  document_id: string;
  notes: string;
  active: boolean;
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type CustomerInput = {
  first_name: string;
  last_name?: string;
  email?: string;
  phone?: string;
  document_id?: string;
  notes?: string;
  active?: boolean;
};

export type CustomerListParams = {
  search?: string;
  active?: boolean;
  page?: number;
  ordering?: string;
};

export function createCustomersApi(client: ApiClient) {
  return {
    list: (params: CustomerListParams = {}) =>
      client.get<Paginated<Customer>>('/api/v1/customers/', { ...params }),

    create: (input: CustomerInput) =>
      client.post<Customer>('/api/v1/customers/', input),

    update: (id: UUID, input: Partial<CustomerInput>) =>
      client.patch<Customer>(`/api/v1/customers/${id}/`, input),

    setActive: (id: UUID, active: boolean) =>
      client.patch<Customer>(`/api/v1/customers/${id}/`, { active }),
  };
}

export type CustomersApi = ReturnType<typeof createCustomersApi>;
```

`web/src/api/services.ts`:

```ts
import type { ApiClient } from './client';
import type { ISODateTime, Paginated, UUID } from './types';

export type Service = {
  id: UUID;
  company: UUID;
  name: string;
  description: string;
  duration_minutes: number;
  price: string;
  buffer_before_minutes: number;
  buffer_after_minutes: number;
  branches: UUID[];
  active: boolean;
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type ServiceInput = {
  name: string;
  description: string;
  duration_minutes: number;
  price: string;
  buffer_before_minutes: number;
  buffer_after_minutes: number;
  branches: UUID[];
  active: boolean;
};

export type ServiceListParams = {
  search?: string;
  active?: boolean;
  branch?: UUID;
  page?: number;
  ordering?: string;
};

export function createServicesApi(client: ApiClient) {
  return {
    list: (params: ServiceListParams = {}) =>
      client.get<Paginated<Service>>('/api/v1/services/', { ...params }),

    create: (input: ServiceInput) =>
      client.post<Service>('/api/v1/services/', input),

    update: (id: UUID, input: Partial<ServiceInput>) =>
      client.patch<Service>(`/api/v1/services/${id}/`, input),
  };
}

export type ServicesApi = ReturnType<typeof createServicesApi>;
```

`web/src/api/team.ts`:

```ts
import type { ApiClient } from './client';
import type { ISODateTime, Paginated, UUID } from './types';

export type Weekday = 0 | 1 | 2 | 3 | 4 | 5 | 6;

export type Worker = {
  id: UUID;
  company: UUID;
  membership: UUID | null;
  first_name: string;
  last_name: string;
  display_name: string;
  email: string;
  phone: string;
  job_title: string;
  color: string;
  branches: UUID[];
  active: boolean;
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type WorkerInput = {
  first_name: string;
  last_name?: string;
  email?: string;
  phone?: string;
  job_title?: string;
  color?: string;
  branches?: UUID[];
  active?: boolean;
  membership?: UUID | null;
};

export type WorkingHours = {
  id: UUID;
  worker: UUID;
  branch: UUID;
  weekday: Weekday;
  start_time: string;
  end_time: string;
};

export type WorkingHoursInput = Omit<WorkingHours, 'id'>;

export type Break = WorkingHours & { label: string };
export type BreakInput = Omit<Break, 'id'>;

export type TimeOff = {
  id: UUID;
  worker: UUID;
  branch: UUID | null;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  reason: string;
};

export type TimeOffInput = Omit<TimeOff, 'id'>;

export type BlockedSlot = {
  id: UUID;
  worker: UUID;
  branch: UUID | null;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  reason: string;
};

export type BlockedSlotInput = Omit<BlockedSlot, 'id'>;

type ListParams = { worker?: UUID; branch?: UUID; page?: number };

type CrudApi<T, TInput> = {
  list(params?: ListParams): Promise<Paginated<T>>;
  create(input: TInput): Promise<T>;
  update(id: UUID, input: Partial<TInput>): Promise<T>;
  remove(id: UUID): Promise<void>;
};

function crud<T, TInput>(client: ApiClient, path: string): CrudApi<T, TInput> {
  return {
    list: (params = {}) => client.get<Paginated<T>>(path, { ...params }),
    create: (input) => client.post<T>(path, input),
    update: (id, input) => client.patch<T>(`${path}${id}/`, input),
    remove: (id) => client.delete<void>(`${path}${id}/`),
  };
}

export function createTeamApi(client: ApiClient) {
  return {
    workers: {
      list: (params: { search?: string; branch?: UUID; active?: boolean; page?: number } = {}) =>
        client.get<Paginated<Worker>>('/api/v1/workers/', { ...params }),
      create: (input: WorkerInput) => client.post<Worker>('/api/v1/workers/', input),
      update: (id: UUID, input: Partial<WorkerInput>) =>
        client.patch<Worker>(`/api/v1/workers/${id}/`, input),
    },
    workingHours: crud<WorkingHours, WorkingHoursInput>(client, '/api/v1/working-hours/'),
    breaks: crud<Break, BreakInput>(client, '/api/v1/breaks/'),
    timeOff: crud<TimeOff, TimeOffInput>(client, '/api/v1/time-off/'),
    blockedSlots: crud<BlockedSlot, BlockedSlotInput>(client, '/api/v1/blocked-slots/'),
  };
}

export type TeamApi = ReturnType<typeof createTeamApi>;
```

- [ ] **Step 5: Implementar informes, marca, claves y runtime**

`web/src/api/summary.ts`:

```ts
import type { ApiClient } from './client';
import type { ISODate, UUID } from './types';

export type ReportRange = {
  date_from: ISODate | null;
  date_to: ISODate | null;
  timezone: string;
  branch: UUID | null;
};

export type SalesTotals = {
  sales: number;
  subtotal: string;
  discounts: string;
  total: string;
  paid: string;
  cost: string;
  profit: string;
  margin_percent: string;
  average_ticket: string;
};

export type PaymentMethodTotal = {
  method: string;
  method_display: string;
  count: number;
  amount: string;
};

export type SalesDay = {
  date: ISODate;
  sales: number;
  subtotal: string;
  discounts: string;
  total: string;
  cost: string;
  profit: string;
};

export type BranchTotal = {
  branch: UUID;
  branch_name: string;
  sales: number;
  subtotal: string;
  discounts: string;
  total: string;
  cost: string;
};

export type TopItem = {
  product?: UUID;
  service?: UUID;
  description: string;
  sku: string | null;
  quantity: string;
  total: string;
  cost: string;
  profit: string;
};

export type SalesSummary = {
  range: ReportRange;
  totals: SalesTotals;
  by_payment_method: PaymentMethodTotal[];
  by_day: SalesDay[];
  by_branch: BranchTotal[];
  top_products: TopItem[];
  top_services: TopItem[];
};

export type CashTotals = {
  sessions: number;
  open: number;
  closed: number;
  opening: string;
  cash_sales: string;
  cash_expenses: string;
  expected: string;
  closing: string;
  difference: string;
  expenses: string;
};

export type CashSessionRow = {
  id: UUID;
  number: string;
  branch: UUID;
  branch_name: string;
  status: string;
  opened_at: string;
  closed_at: string | null;
  opening_amount: string;
  cash_sales: string;
  cash_expenses: string;
  expected: string;
  closing_amount: string | null;
  difference: string | null;
};

export type ExpenseTotal = { category: string; total: string };
export type ExpenseMethodTotal = { method: string; method_display: string; total: string };

export type CashSummary = {
  range: ReportRange;
  totals: CashTotals;
  sessions: CashSessionRow[];
  expenses_by_category: ExpenseTotal[];
  expenses_by_method: ExpenseMethodTotal[];
};

export type SummaryParams = { date_from: ISODate; date_to: ISODate; branch?: UUID };

export function createSummaryApi(client: ApiClient) {
  return {
    sales: (params: SummaryParams) =>
      client.get<SalesSummary>('/api/v1/reports/sales-summary/', { ...params }),
    cash: (params: SummaryParams) =>
      client.get<CashSummary>('/api/v1/reports/cash-summary/', { ...params }),
  };
}

export type SummaryApi = ReturnType<typeof createSummaryApi>;
```

`web/src/api/branding.ts`:

```ts
import type { ApiClient } from './client';
import type { ThemeMode } from './types';

export type Branding = {
  display_name: string;
  logo_url: string;
  primary_color: string;
  secondary_color: string;
  theme_mode: ThemeMode;
  booking_url: string;
  name: string;
  slug: string;
  can_manage: boolean;
};

export type BrandingInput = {
  display_name?: string;
  slug?: string;
  primary_color?: string;
  secondary_color?: string;
  theme_mode?: ThemeMode;
};

export function createBrandingApi(client: ApiClient) {
  return {
    get: () => client.get<Branding>('/api/v1/company/branding/'),
    update: (input: BrandingInput) =>
      client.patch<Branding>('/api/v1/company/branding/', input),
    uploadLogo: (file: File) => {
      const form = new FormData();
      form.append('logo', file);
      return client.postForm<Branding>('/api/v1/company/branding/logo/', form);
    },
    removeLogo: () => client.delete<Branding>('/api/v1/company/branding/logo/'),
  };
}

export type BrandingApi = ReturnType<typeof createBrandingApi>;
```

`web/src/api/queryKeys.ts`:

```ts
import type { BookingListParams, AvailabilityParams } from './agenda';
import type { CustomerListParams } from './customers';
import type { ServiceListParams } from './services';
import type { SummaryParams } from './summary';
import type { UUID } from './types';

const list = (name: string, companyId: UUID, params: object) => [name, companyId, params] as const;

export const queryKeys = {
  bookings: (companyId: UUID, params: BookingListParams) => list('bookings', companyId, params),
  availability: (companyId: UUID, params: AvailabilityParams) =>
    list('availability', companyId, params),
  customers: (companyId: UUID, params: CustomerListParams) => list('customers', companyId, params),
  customerBookings: (companyId: UUID, customerId: UUID) =>
    ['customer-bookings', companyId, customerId] as const,
  services: (companyId: UUID, params: ServiceListParams) => list('services', companyId, params),
  workers: (companyId: UUID, params: object) => list('workers', companyId, params),
  workingHours: (companyId: UUID, workerId: UUID) =>
    ['working-hours', companyId, workerId] as const,
  breaks: (companyId: UUID, workerId: UUID) => ['breaks', companyId, workerId] as const,
  timeOff: (companyId: UUID, workerId: UUID) => ['time-off', companyId, workerId] as const,
  blockedSlots: (companyId: UUID, workerId: UUID) =>
    ['blocked-slots', companyId, workerId] as const,
  salesSummary: (companyId: UUID, params: SummaryParams) =>
    list('sales-summary', companyId, params),
  cashSummary: (companyId: UUID, params: SummaryParams) => list('cash-summary', companyId, params),
  branding: (companyId: UUID) => ['branding', companyId] as const,
};
```

`web/src/api/runtime.ts` (agregar al final, después de configurar refresh y unauthorized):

```ts
import { createAgendaApi } from './agenda';
import { createBrandingApi } from './branding';
import { createCustomersApi } from './customers';
import { createServicesApi } from './services';
import { createSummaryApi } from './summary';
import { createTeamApi } from './team';

export const agendaApi = createAgendaApi(apiClient);
export const customersApi = createCustomersApi(apiClient);
export const servicesApi = createServicesApi(apiClient);
export const teamApi = createTeamApi(apiClient);
export const summaryApi = createSummaryApi(apiClient);
export const brandingApi = createBrandingApi(apiClient);
```

- [ ] **Step 6: Ejecutar las pruebas y verificar**

Run: `cd web && npm run test -- src/api/domain.test.ts`

Expected: 8 tests PASS.

- [ ] **Step 7: Verificar tipos y lint**

Run:

```bash
cd web
npm run build
npm run lint
```

Expected: sin errores.

- [ ] **Step 8: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/api
git commit -m "feat(web): add domain API modules and company-scoped query keys"
```

---

### Task 9: Fechas, zona horaria y formato

**Files:**
- Create: `web/src/lib/dates.ts`, `web/src/lib/dates.test.ts`, `web/src/lib/format.ts`, `web/src/lib/format.test.ts`

**Interfaces:**
- Produces:
  - `todayInZone`, `shiftDate`, `weekRange`, `formatTime`, `formatDateLabel`, `formatDateTime`, `formatDateISO`, `dateTimeLocalToISO`, `isoToDateTimeLocal`.
  - `WEEKDAYS`, `weekdayLabel`, `BOOKING_STATUS_LABELS`, `formatMoney`, `formatPercent`.

- [ ] **Step 1: Escribir las pruebas de fechas y formato**

`web/src/lib/dates.test.ts`:

```ts
import { describe, expect, test } from 'vitest';

import {
  dateTimeLocalToISO,
  formatTime,
  isoToDateTimeLocal,
  shiftDate,
  todayInZone,
  weekRange,
} from './dates';

describe('fechas de agenda', () => {
  test('calcula el día local de la sucursal y no el UTC', () => {
    expect(todayInZone('America/Santiago', new Date('2026-11-12T02:00:00Z'))).toBe('2026-11-11');
    expect(todayInZone('America/Santiago', new Date('2026-11-11T12:00:00Z'))).toBe('2026-11-11');
  });

  test('la semana corre de lunes a domingo', () => {
    expect(weekRange('2026-11-11')).toEqual({ date_from: '2026-11-09', date_to: '2026-11-15' });
    expect(weekRange('2026-11-15')).toEqual({ date_from: '2026-11-09', date_to: '2026-11-15' });
  });

  test('desplaza días cruzando meses', () => {
    expect(shiftDate('2026-11-30', 1)).toBe('2026-12-01');
    expect(shiftDate('2026-01-01', -1)).toBe('2025-12-31');
  });

  test('convierte hora local de verano e invierno a UTC', () => {
    expect(dateTimeLocalToISO('2026-01-15T10:00', 'America/Santiago')).toBe(
      '2026-01-15T13:00:00.000Z',
    );
    expect(dateTimeLocalToISO('2026-07-15T10:00', 'America/Santiago')).toBe(
      '2026-07-15T14:00:00.000Z',
    );
  });

  test('convierte un instante UTC a hora local de la sucursal', () => {
    expect(isoToDateTimeLocal('2026-01-15T13:00:00Z', 'America/Santiago')).toBe('2026-01-15T10:00');
    expect(formatTime('2026-07-15T14:00:00Z', 'America/Santiago')).toBe('10:00');
  });
});
```

`web/src/lib/format.test.ts`:

```ts
import { describe, expect, test } from 'vitest';

import { BOOKING_STATUS_LABELS, formatMoney, formatPercent, weekdayLabel } from './format';

describe('formato', () => {
  test('formatea montos y porcentajes en español de Chile', () => {
    expect(formatMoney('12000.00')).toBe('$ 12.000');
    expect(formatMoney(1234.5)).toBe('$ 1.234,5');
    expect(formatPercent('37.50')).toBe('37,5 %');
  });

  test('traduce estados y días', () => {
    expect(BOOKING_STATUS_LABELS.no_show).toBe('No asistió');
    expect(BOOKING_STATUS_LABELS.confirmed).toBe('Confirmada');
    expect(weekdayLabel(0)).toBe('Lunes');
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

Run: `cd web && npm run test -- src/lib/dates.test.ts src/lib/format.test.ts`

Expected: FAIL porque los módulos no existen.

- [ ] **Step 3: Implementar utilidades de fecha y zona horaria**

`web/src/lib/dates.ts`:

```ts
type ZoneParts = {
  year: string;
  month: string;
  day: string;
  hour: string;
  minute: string;
  second: string;
};

function partsInZone(date: Date, timeZone: string): ZoneParts {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
  const values: Record<string, string> = {};
  formatter.formatToParts(date).forEach((part) => {
    if (part.type !== 'literal') values[part.type] = part.value;
  });
  return {
    year: values.year,
    month: values.month,
    day: values.day,
    hour: values.hour,
    minute: values.minute,
    second: values.second,
  };
}

function zoneOffsetMs(date: Date, timeZone: string): number {
  const parts = partsInZone(date, timeZone);
  const asUtc = Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour),
    Number(parts.minute),
    Number(parts.second),
  );
  return asUtc - date.getTime();
}

export function todayInZone(timeZone: string, now = new Date()): string {
  const parts = partsInZone(now, timeZone);
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function formatDateISO(value: string, timeZone: string): string {
  const parts = partsInZone(new Date(value), timeZone);
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function shiftDate(dateISO: string, days: number): string {
  const [year, month, day] = dateISO.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day + days));
  return date.toISOString().slice(0, 10);
}

export function weekRange(dateISO: string): { date_from: string; date_to: string } {
  const [year, month, day] = dateISO.split('-').map(Number);
  const weekday = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  const offset = weekday === 0 ? -6 : 1 - weekday;
  const monday = shiftDate(dateISO, offset);
  return { date_from: monday, date_to: shiftDate(monday, 6) };
}

export function formatTime(value: string, timeZone: string): string {
  return new Intl.DateTimeFormat('es-CL', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(new Date(value));
}

export function formatDateLabel(dateISO: string): string {
  const [year, month, day] = dateISO.split('-').map(Number);
  return new Intl.DateTimeFormat('es-CL', {
    timeZone: 'UTC',
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  }).format(new Date(Date.UTC(year, month - 1, day, 12)));
}

export function formatDateTime(value: string, timeZone: string): string {
  const dateISO = formatDateISO(value, timeZone);
  return `${formatDateLabel(dateISO)} · ${formatTime(value, timeZone)}`;
}

export function dateTimeLocalToISO(value: string, timeZone: string): string {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) {
    throw new Error('Fecha y hora inválidas.');
  }
  const [datePart, timePart] = value.split('T');
  const [year, month, day] = datePart.split('-').map(Number);
  const [hour, minute] = timePart.split(':').map(Number);
  const naiveUtc = Date.UTC(year, month - 1, day, hour, minute, 0);
  const firstOffset = zoneOffsetMs(new Date(naiveUtc), timeZone);
  let result = new Date(naiveUtc - firstOffset);
  const secondOffset = zoneOffsetMs(result, timeZone);
  if (secondOffset !== firstOffset) result = new Date(naiveUtc - secondOffset);
  return result.toISOString();
}

export function isoToDateTimeLocal(value: string, timeZone: string): string {
  const parts = partsInZone(new Date(value), timeZone);
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}
```

- [ ] **Step 4: Implementar formato de textos y montos**

`web/src/lib/format.ts`:

```ts
import type { BookingStatus } from '../api/agenda';

export const WEEKDAYS = [
  'Lunes',
  'Martes',
  'Miércoles',
  'Jueves',
  'Viernes',
  'Sábado',
  'Domingo',
] as const;

export function weekdayLabel(index: number): string {
  return WEEKDAYS[index] ?? '—';
}

export const BOOKING_STATUS_LABELS: Record<BookingStatus, string> = {
  scheduled: 'Agendada',
  confirmed: 'Confirmada',
  completed: 'Completada',
  canceled: 'Cancelada',
  no_show: 'No asistió',
};

const decimal = new Intl.NumberFormat('es-CL', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export function formatMoney(value: string | number | null | undefined): string {
  const numeric = typeof value === 'number' ? value : Number.parseFloat(value ?? '0');
  return `$ ${decimal.format(Number.isFinite(numeric) ? numeric : 0)}`;
}

export function formatPercent(value: string | number | null | undefined): string {
  const numeric = typeof value === 'number' ? value : Number.parseFloat(value ?? '0');
  const formatted = new Intl.NumberFormat('es-CL', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(numeric) ? numeric : 0);
  return `${formatted} %`;
}
```

- [ ] **Step 5: Ejecutar las pruebas y verificar**

Run: `cd web && npm run test -- src/lib/dates.test.ts src/lib/format.test.ts`

Expected: 7 tests PASS.

- [ ] **Step 6: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/lib/dates.ts web/src/lib/dates.test.ts web/src/lib/format.ts web/src/lib/format.test.ts
git commit -m "feat(web): add branch-timezone date utilities and Spanish formatting"
```

---

### Task 10: Agenda con vistas día y semana

**Files:**
- Create: `web/src/features/agenda/AgendaPage.tsx`, `web/src/features/agenda/AgendaCalendar.tsx`, `web/src/features/agenda/BookingDetailDialog.tsx`, `web/src/features/agenda/agendaLayout.ts`, `web/src/features/agenda/AgendaPage.test.tsx`, `web/src/features/agenda/agendaLayout.test.ts`
- Modify: `web/src/app/router.tsx`

**Interfaces:**
- Consumes: `agendaApi`, `teamApi`, `servicesApi`, `queryKeys`, `useAuth`, `todayInZone`, `weekRange`, `formatTime`, `formatDateLabel`, `BOOKING_STATUS_LABELS`.
- Produces:
  - `AgendaPage` y `AgendaCalendar({ view, anchorDate, dateFrom, timezone, workers, bookings, onSelectBooking })`.
  - `BookingDetailDialog({ booking, timezone, onClose })` de solo lectura; la tarea 12 agrega acciones.
  - `hourBounds`, `bookingBlockStyle`, `bookingsForWorker`, `groupWeek`, `workersForColumns` en `agendaLayout.ts`.

- [ ] **Step 1: Escribir las pruebas de la agenda**

`web/src/features/agenda/agendaLayout.test.ts`:

```ts
import { describe, expect, test } from 'vitest';

import type { Booking } from '../../api/agenda';
import { bookingBlockStyle, groupWeek, hourBounds } from './agendaLayout';

const booking = (overrides: Partial<Booking> = {}): Booking => ({
  id: 'booking-1',
  company: 'company-a',
  branch: 'branch-1',
  branch_name: 'Providencia',
  customer: 'customer-1',
  customer_name: 'Ana Díaz',
  customer_email: 'ana@example.com',
  service: 'service-1',
  service_name: 'Corte',
  worker: 'worker-1',
  worker_name: 'Paula Rojas',
  start_at: '2026-01-15T13:00:00Z',
  end_at: '2026-01-15T13:30:00Z',
  duration_minutes: 30,
  price: '12000.00',
  status: 'scheduled',
  status_display: 'Agendada',
  source: 'staff',
  source_display: 'Equipo',
  notes: '',
  public_code: 'ABCDEFGHIJ',
  canceled_at: null,
  canceled_reason: '',
  created_at: '2026-11-11T12:00:00Z',
  updated_at: '2026-11-11T12:00:00Z',
  ...overrides,
});

describe('agendaLayout', () => {
  test('amplía el eje cuando hay reservas fuera del horario por defecto', () => {
    expect(hourBounds([], 'America/Santiago')).toEqual({ startHour: 8, endHour: 20 });
    const early = booking({ start_at: '2026-01-15T10:00:00Z', end_at: '2026-01-15T10:30:00Z' });
    const late = booking({ id: 'b2', start_at: '2026-01-15T23:30:00Z', end_at: '2026-01-16T00:00:00Z' });
    expect(hourBounds([early, late], 'America/Santiago')).toEqual({ startHour: 7, endHour: 21 });
  });

  test('posiciona el bloque según la hora local de la sucursal', () => {
    const style = bookingBlockStyle(booking(), 8, 20, 'America/Santiago');
    expect(Number.parseFloat(style.top)).toBeCloseTo(16.67, 2);
    expect(Number.parseFloat(style.height)).toBeCloseTo(4.17, 2);
  });

  test('agrupa la semana por fecha local', () => {
    const nextDay = booking({
      id: 'booking-2',
      start_at: '2026-01-16T13:00:00Z',
      end_at: '2026-01-16T13:30:00Z',
    });
    const week = groupWeek([booking(), nextDay], '2026-01-12', 'America/Santiago');
    expect(week).toHaveLength(7);
    expect(week[3].bookings.map((item) => item.id)).toEqual(['booking-1']);
    expect(week[4].bookings.map((item) => item.id)).toEqual(['booking-2']);
  });
});
```

`web/src/features/agenda/AgendaPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { server } from '../../test/server';
import { makeAuthValue } from '../../test/factories';
import { AgendaPage } from './AgendaPage';

const bookingFixture = {
  id: 'booking-1',
  company: 'company-a',
  branch: 'branch-1',
  branch_name: 'Providencia',
  customer: 'customer-1',
  customer_name: 'Ana Díaz',
  customer_email: 'ana@example.com',
  service: 'service-1',
  service_name: 'Corte de cabello',
  worker: 'worker-1',
  worker_name: 'Paula Rojas',
  start_at: '2026-11-12T13:00:00Z',
  end_at: '2026-11-12T13:30:00Z',
  duration_minutes: 30,
  price: '12000.00',
  status: 'scheduled',
  status_display: 'Agendada',
  source: 'staff',
  source_display: 'Equipo',
  notes: '',
  public_code: 'ABCDEFGHIJ',
  canceled_at: null,
  canceled_reason: '',
  created_at: '2026-11-11T12:00:00Z',
  updated_at: '2026-11-11T12:00:00Z',
};

function renderAgenda() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <AgendaPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function useAgendaHandlers(bookingUrls: string[] = []) {
  server.use(
    http.get('http://api.test/api/v1/workers/', () =>
      HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: 'worker-1',
            company: 'company-a',
            membership: null,
            first_name: 'Paula',
            last_name: 'Rojas',
            display_name: 'Paula Rojas',
            email: '',
            phone: '',
            job_title: 'Estilista',
            color: '#10b981',
            branches: ['branch-1'],
            active: true,
            created_at: '2026-11-11T12:00:00Z',
            updated_at: '2026-11-11T12:00:00Z',
          },
        ],
      }),
    ),
    http.get('http://api.test/api/v1/services/', () =>
      HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: 'service-1',
            company: 'company-a',
            name: 'Corte de cabello',
            description: '',
            duration_minutes: 30,
            price: '12000.00',
            buffer_before_minutes: 0,
            buffer_after_minutes: 0,
            branches: ['branch-1'],
            active: true,
            created_at: '2026-11-11T12:00:00Z',
            updated_at: '2026-11-11T12:00:00Z',
          },
        ],
      }),
    ),
    http.get('http://api.test/api/v1/bookings/', ({ request }) => {
      bookingUrls.push(request.url);
      return HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [bookingFixture],
      });
    }),
  );
}

describe('AgendaPage', () => {
  test('consulta la agenda de la sucursal y muestra la reserva', async () => {
    const urls: string[] = [];
    useAgendaHandlers(urls);
    renderAgenda();

    expect(await screen.findByText(/Ana Díaz/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Paula Rojas' })).toBeInTheDocument();
    expect(urls[0]).toContain('branch=branch-1');
    expect(urls[0]).toContain('date=');
  });

  test('abre el detalle de la reserva', async () => {
    useAgendaHandlers();
    renderAgenda();

    await userEvent.click(await screen.findByRole('button', { name: /Ana Díaz/ }));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Corte de cabello · Ana Díaz')).toBeInTheDocument();
  });

  test('la vista semanal consulta el rango de lunes a domingo', async () => {
    const urls: string[] = [];
    useAgendaHandlers(urls);
    renderAgenda();
    await screen.findByText(/Ana Díaz/);

    await userEvent.click(screen.getByRole('button', { name: 'Semana' }));

    await waitFor(() => expect(urls.at(-1)).toContain('date_from='));
    expect(urls.at(-1)).toContain('date_to=');
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

Run:

```bash
cd web
npm run test -- src/features/agenda/agendaLayout.test.ts src/features/agenda/AgendaPage.test.tsx
```

Expected: FAIL porque los módulos no existen.

- [ ] **Step 3: Implementar el cálculo de la agenda**

`web/src/features/agenda/agendaLayout.ts`:

```ts
import type { Booking } from '../../api/agenda';
import type { Worker } from '../../api/team';
import { formatDateISO, formatTime, shiftDate } from '../../lib/dates';

const DEFAULT_START_HOUR = 8;
const DEFAULT_END_HOUR = 20;

function localMinutes(value: string, timeZone: string): number {
  const [hour, minute] = formatTime(value, timeZone).split(':').map(Number);
  return hour * 60 + minute;
}

export function hourBounds(
  bookings: Booking[],
  timeZone: string,
): { startHour: number; endHour: number } {
  let startHour = DEFAULT_START_HOUR;
  let endHour = DEFAULT_END_HOUR;
  bookings.forEach((booking) => {
    const start = localMinutes(booking.start_at, timeZone);
    const end = start + booking.duration_minutes;
    startHour = Math.min(startHour, Math.floor(start / 60));
    if (end > start) endHour = Math.max(endHour, Math.ceil(end / 60));
  });
  return {
    startHour: Math.max(0, startHour),
    endHour: Math.min(24, Math.max(startHour + 1, endHour)),
  };
}

export function bookingBlockStyle(
  booking: Booking,
  startHour: number,
  endHour: number,
  timeZone: string,
): { top: string; height: string } {
  const total = (endHour - startHour) * 60;
  const start = localMinutes(booking.start_at, timeZone) - startHour * 60;
  const top = Math.max(0, Math.min(100, (start / total) * 100));
  const height = Math.max(1.5, Math.min(100 - top, (booking.duration_minutes / total) * 100));
  return { top: `${top}%`, height: `${height}%` };
}

export function bookingsForWorker(bookings: Booking[], workerId: string): Booking[] {
  return bookings
    .filter((booking) => booking.worker === workerId)
    .sort((first, second) => first.start_at.localeCompare(second.start_at));
}

export function groupWeek(
  bookings: Booking[],
  dateFrom: string,
  timeZone: string,
): { date: string; bookings: Booking[] }[] {
  return Array.from({ length: 7 }, (_, index) => {
    const date = shiftDate(dateFrom, index);
    return {
      date,
      bookings: bookings
        .filter((booking) => formatDateISO(booking.start_at, timeZone) === date)
        .sort((first, second) => first.start_at.localeCompare(second.start_at)),
    };
  });
}

export function workersForColumns(workers: Worker[], selectedWorker: string): Worker[] {
  return selectedWorker ? workers.filter((worker) => worker.id === selectedWorker) : workers;
}
```

- [ ] **Step 4: Implementar el calendario**

`web/src/features/agenda/AgendaCalendar.tsx`:

```tsx
import type { Booking } from '../../api/agenda';
import type { Worker } from '../../api/team';
import { Badge } from '../../components/ui/Badge';
import { formatDateLabel, formatTime } from '../../lib/dates';
import { BOOKING_STATUS_LABELS } from '../../lib/format';
import { bookingBlockStyle, bookingsForWorker, groupWeek, hourBounds } from './agendaLayout';

type Props = {
  view: 'day' | 'week';
  anchorDate: string;
  dateFrom: string;
  timezone: string;
  workers: Worker[];
  bookings: Booking[];
  onSelectBooking: (booking: Booking) => void;
};

function workerColor(worker: Worker): string {
  return /^#[0-9A-Fa-f]{6}$/.test(worker.color) ? worker.color : 'var(--brand-primary)';
}

export function AgendaCalendar({
  view,
  anchorDate,
  dateFrom,
  timezone,
  workers,
  bookings,
  onSelectBooking,
}: Props) {
  if (view === 'week') {
    const days = groupWeek(bookings, dateFrom, timezone);
    return (
      <div className="overflow-x-auto">
        <div className="grid min-w-[840px] grid-cols-7 gap-2">
          {days.map((day) => (
            <section key={day.date} className="rounded-lg border border-line bg-panel p-2">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                {formatDateLabel(day.date)}
              </h2>
              {day.bookings.length === 0 ? (
                <p className="py-4 text-center text-xs text-muted">Sin reservas</p>
              ) : (
                <ul className="space-y-2">
                  {day.bookings.map((booking) => (
                    <li key={booking.id}>
                      <button
                        type="button"
                        onClick={() => onSelectBooking(booking)}
                        className="w-full rounded-md border-l-4 bg-surface p-2 text-left text-xs transition hover:bg-brand-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
                        style={{ borderLeftColor: workerColor(workers.find((worker) => worker.id === booking.worker) ?? workers[0]) }}
                      >
                        <span className="block font-semibold text-ink">
                          {formatTime(booking.start_at, timezone)} · {booking.customer_name}
                        </span>
                        <span className="block text-muted">{booking.service_name}</span>
                        <span className="mt-1 block">
                          <Badge tone={booking.status}>{BOOKING_STATUS_LABELS[booking.status]}</Badge>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>
      </div>
    );
  }

  const { startHour, endHour } = hourBounds(bookings, timezone);
  const hours = Array.from({ length: endHour - startHour }, (_, index) => startHour + index);
  const gridHeight = (endHour - startHour) * 64;
  const columns =
    workers.length > 0
      ? workers.map((worker) => ({
          id: worker.id,
          label: worker.display_name,
          color: workerColor(worker),
          bookings: bookingsForWorker(bookings, worker.id),
        }))
      : [
          {
            id: 'all',
            label: 'Agenda',
            color: 'var(--brand-primary)',
            bookings: [...bookings].sort((first, second) =>
              first.start_at.localeCompare(second.start_at),
            ),
          },
        ];

  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-panel">
      <div
        className="grid min-w-[640px] gap-px bg-line"
        style={{ gridTemplateColumns: `64px repeat(${columns.length}, minmax(140px, 1fr))` }}
      >
        <div className="bg-panel p-2 text-xs font-semibold text-muted">
          {formatDateLabel(anchorDate)}
        </div>
        {columns.map((column) => (
          <h2 key={column.id} className="bg-panel p-2 text-center text-sm font-semibold text-ink">
            {column.label}
          </h2>
        ))}

        <div className="relative bg-panel" style={{ height: gridHeight }}>
          {hours.map((hour, index) => (
            <span
              key={hour}
              className="absolute right-2 -translate-y-1/2 text-xs text-muted"
              style={{ top: index * 64 }}
            >
              {String(hour).padStart(2, '0')}:00
            </span>
          ))}
        </div>

        {columns.map((column) => (
          <div key={column.id} className="relative bg-panel" style={{ height: gridHeight }}>
            {hours.map((hour, index) => (
              <span
                key={hour}
                aria-hidden="true"
                className="absolute inset-x-0 border-t border-line/70"
                style={{ top: index * 64 }}
              />
            ))}
            {column.bookings.map((booking) => (
              <button
                type="button"
                key={booking.id}
                onClick={() => onSelectBooking(booking)}
                className="absolute inset-x-1 overflow-hidden rounded-md border-l-4 bg-surface p-1.5 text-left text-xs transition hover:bg-brand-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
                style={{
                  ...bookingBlockStyle(booking, startHour, endHour, timezone),
                  borderLeftColor: column.color,
                }}
              >
                <span className="block font-semibold text-ink">
                  {formatTime(booking.start_at, timezone)} {booking.customer_name}
                </span>
                <span className="block truncate text-muted">{booking.service_name}</span>
                <span className="mt-1 block">
                  <Badge tone={booking.status}>{BOOKING_STATUS_LABELS[booking.status]}</Badge>
                </span>
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Implementar la pantalla y el detalle de solo lectura**

`web/src/features/agenda/BookingDetailDialog.tsx`:

```tsx
import type { Booking } from '../../api/agenda';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { formatDateTime } from '../../lib/dates';
import { BOOKING_STATUS_LABELS, formatMoney } from '../../lib/format';

export function BookingDetailDialog({
  booking,
  timezone,
  onClose,
}: {
  booking: Booking | null;
  timezone: string;
  onClose: () => void;
}) {
  return (
    <Dialog
      open={Boolean(booking)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Detalle de reserva"
      description={booking ? `${booking.service_name} · ${booking.customer_name}` : undefined}
      footer={
        <Button variant="secondary" onClick={onClose}>
          Cerrar
        </Button>
      }
    >
      {booking ? (
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-muted">Inicio</dt>
            <dd className="text-ink">{formatDateTime(booking.start_at, timezone)}</dd>
          </div>
          <div>
            <dt className="text-muted">Fin</dt>
            <dd className="text-ink">{formatDateTime(booking.end_at, timezone)}</dd>
          </div>
          <div>
            <dt className="text-muted">Trabajador</dt>
            <dd className="text-ink">{booking.worker_name}</dd>
          </div>
          <div>
            <dt className="text-muted">Sucursal</dt>
            <dd className="text-ink">{booking.branch_name}</dd>
          </div>
          <div>
            <dt className="text-muted">Precio</dt>
            <dd className="text-ink">{formatMoney(booking.price)}</dd>
          </div>
          <div>
            <dt className="text-muted">Estado</dt>
            <dd>
              <Badge tone={booking.status}>{BOOKING_STATUS_LABELS[booking.status]}</Badge>
            </dd>
          </div>
          <div className="col-span-2">
            <dt className="text-muted">Notas</dt>
            <dd className="text-ink">{booking.notes || 'Sin notas'}</dd>
          </div>
        </dl>
      ) : null}
    </Dialog>
  );
}
```

`web/src/features/agenda/AgendaPage.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';

import type { Booking, BookingListParams, BookingStatus } from '../../api/agenda';
import { agendaApi, servicesApi, teamApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { PageHeader } from '../../components/ui/PageHeader';
import { Pagination } from '../../components/ui/Pagination';
import { Skeleton } from '../../components/ui/Skeleton';
import { todayInZone, weekRange, shiftDate, formatDateLabel } from '../../lib/dates';
import { AgendaCalendar } from './AgendaCalendar';
import { workersForColumns } from './agendaLayout';
import { BookingDetailDialog } from './BookingDetailDialog';

const STATUS_OPTIONS: { value: BookingStatus | ''; label: string }[] = [
  { value: '', label: 'Todos los estados' },
  { value: 'scheduled', label: 'Agendadas' },
  { value: 'confirmed', label: 'Confirmadas' },
  { value: 'completed', label: 'Completadas' },
  { value: 'canceled', label: 'Canceladas' },
  { value: 'no_show', label: 'No asistió' },
];

export function AgendaPage() {
  const { company, bootstrap } = useAuth();
  const branches = useMemo(
    () => (bootstrap?.branches ?? []).filter((branch) => branch.active),
    [bootstrap],
  );
  const [branchId, setBranchId] = useState(branches[0]?.id ?? '');
  const branch = branches.find((item) => item.id === branchId) ?? branches[0];
  const timezone = branch?.timezone ?? 'America/Santiago';

  const [view, setView] = useState<'day' | 'week'>('day');
  const [anchorDate, setAnchorDate] = useState(() => todayInZone(timezone));
  const [workerId, setWorkerId] = useState('');
  const [serviceId, setServiceId] = useState('');
  const [status, setStatus] = useState<BookingStatus | ''>('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Booking | null>(null);

  const workersQuery = useQuery({
    queryKey: queryKeys.workers(company?.id ?? '', { branch: branchId, active: true }),
    queryFn: () => teamApi.workers.list({ branch: branchId, active: true, page: 1 }),
    enabled: Boolean(company && branchId),
  });
  const servicesQuery = useQuery({
    queryKey: queryKeys.services(company?.id ?? '', { active: true }),
    queryFn: () => servicesApi.list({ active: true, page: 1 }),
    enabled: Boolean(company && branchId),
  });

  const range = view === 'day' ? { date: anchorDate } : weekRange(anchorDate);
  const params: BookingListParams = {
    branch: branchId,
    ...range,
    worker: workerId || undefined,
    service: serviceId || undefined,
    status: status || undefined,
    page,
    ordering: 'start_at',
  };
  const bookingsQuery = useQuery({
    queryKey: queryKeys.bookings(company?.id ?? '', params),
    queryFn: () => agendaApi.listBookings(params),
    enabled: Boolean(company && branchId),
  });

  const workers = workersQuery.data?.results ?? [];
  const services = servicesQuery.data?.results ?? [];
  const branchServices = services.filter(
    (service) => service.branches.length === 0 || service.branches.includes(branchId),
  );
  const bookings = bookingsQuery.data?.results ?? [];
  const columns = workersForColumns(workers, workerId);

  function changeBranch(nextBranchId: string) {
    setBranchId(nextBranchId);
    const nextBranch = branches.find((item) => item.id === nextBranchId);
    setAnchorDate(todayInZone(nextBranch?.timezone ?? timezone));
    setWorkerId('');
    setServiceId('');
    setStatus('');
    setPage(1);
  }

  function moveDate(days: number) {
    setAnchorDate((current) => shiftDate(current, view === 'day' ? days : days * 7));
    setPage(1);
  }

  function changeView(next: 'day' | 'week') {
    setView(next);
    setPage(1);
  }

  const periodLabel =
    view === 'day'
      ? formatDateLabel(anchorDate)
      : `${formatDateLabel(weekRange(anchorDate).date_from)} – ${formatDateLabel(weekRange(anchorDate).date_to)}`;

  if (branches.length === 0) {
    return (
      <EmptyState
        title="No hay sucursales activas"
        description="La agenda necesita una sucursal activa con zona horaria configurada."
      />
    );
  }

  return (
    <section>
      <PageHeader
        title="Agenda"
        description={`Horarios en ${timezone} · ${periodLabel}`}
      />

      <div className="mb-4 flex flex-wrap items-end gap-2">
        <label className="text-sm text-muted">
          Sucursal
          <select
            className="mt-1 block rounded-md border border-line bg-panel px-2 py-1.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
            value={branchId}
            onChange={(event) => changeBranch(event.target.value)}
          >
            {branches.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-muted">
          Trabajador
          <select
            className="mt-1 block rounded-md border border-line bg-panel px-2 py-1.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
            value={workerId}
            onChange={(event) => {
              setWorkerId(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Todos</option>
            {workers.map((worker) => (
              <option key={worker.id} value={worker.id}>
                {worker.display_name}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-muted">
          Servicio
          <select
            className="mt-1 block rounded-md border border-line bg-panel px-2 py-1.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
            value={serviceId}
            onChange={(event) => {
              setServiceId(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Todos</option>
            {branchServices.map((service) => (
              <option key={service.id} value={service.id}>
                {service.name}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-muted">
          Estado
          <select
            className="mt-1 block rounded-md border border-line bg-panel px-2 py-1.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as BookingStatus | '');
              setPage(1);
            }}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Vista" className="flex rounded-md border border-line bg-panel">
            <Button variant={view === 'day' ? 'primary' : 'ghost'} onClick={() => changeView('day')}>
              Día
            </Button>
            <Button variant={view === 'week' ? 'primary' : 'ghost'} onClick={() => changeView('week')}>
              Semana
            </Button>
          </div>
          <Button variant="secondary" onClick={() => moveDate(-1)}>
            Anterior
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              setAnchorDate(todayInZone(timezone));
              setPage(1);
            }}
          >
            Hoy
          </Button>
          <Button variant="secondary" onClick={() => moveDate(1)}>
            Siguiente
          </Button>
        </div>
      </div>

      {bookingsQuery.isError ? (
        <ErrorBanner
          message={bookingsQuery.error instanceof Error ? bookingsQuery.error.message : 'No se pudo cargar la agenda.'}
          onRetry={() => void bookingsQuery.refetch()}
        />
      ) : null}

      <div className="mt-4">
        {workersQuery.isLoading || bookingsQuery.isLoading ? (
          <Skeleton rows={6} />
        ) : bookings.length === 0 ? (
          <EmptyState
            title={view === 'day' ? 'Sin reservas para este día' : 'Sin reservas para esta semana'}
            description={
              status || workerId || serviceId
                ? 'Prueba quitando filtros o moviéndote a otra fecha.'
                : 'Crea una reserva para comenzar a llenar la agenda.'
            }
          />
        ) : (
          <AgendaCalendar
            view={view}
            anchorDate={anchorDate}
            dateFrom={weekRange(anchorDate).date_from}
            timezone={timezone}
            workers={columns}
            bookings={bookings}
            onSelectBooking={setSelected}
          />
        )}
      </div>

      {bookingsQuery.data ? (
        <Pagination page={page} count={bookingsQuery.data.count} onPage={setPage} />
      ) : null}

      <BookingDetailDialog
        booking={selected}
        timezone={timezone}
        onClose={() => setSelected(null)}
      />
    </section>
  );
}
```

Si `workers` llega vacío (por ejemplo, recepción sin `workforce.read`), el calendario del día muestra una sola columna «Agenda» con todas las reservas de la sucursal en lugar de bloquear la pantalla.

- [ ] **Step 6: Registrar la ruta real**

En `web/src/app/router.tsx`, importar `AgendaPage` y reemplazar el placeholder de agenda:

```tsx
import { AgendaPage } from '../features/agenda/AgendaPage';
```

```tsx
{
  path: 'agenda',
  element: (
    <RequirePermission permission="bookings.read">
      <AgendaPage />
    </RequirePermission>
  ),
},
```

- [ ] **Step 7: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test -- src/features/agenda
npm run build
npm run lint
```

Expected: 6 tests PASS; build y lint sin errores.

- [ ] **Step 8: Validación visual**

Con datos locales, revisar en 1280 px y 768 px, claro y oscuro:

- Eje horario, columnas por trabajador y bloques alineados.
- Vista semanal con siete columnas y desplazamiento horizontal en 768 px.
- Reservas clicables con teclado y detalle con foco atrapado.

- [ ] **Step 9: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/features/agenda web/src/app/router.tsx
git commit -m "feat(web): add day and week agenda calendar with booking detail"
```

---

### Task 11: Alta de reserva con disponibilidad real

**Files:**
- Create: `web/src/features/agenda/BookingCreateDialog.tsx`, `web/src/features/agenda/BookingCreateDialog.test.tsx`
- Modify: `web/src/features/agenda/AgendaPage.tsx`

**Interfaces:**
- Consumes: `agendaApi`, `customersApi`, `servicesApi`, `teamApi`, `queryKeys`, `useDebouncedValue`, `dateTimeLocalToISO` no aplica (los cupos ya vienen en UTC), `Button`, `Dialog`, `Field`, `Input`, `Select`, `Textarea`, `ErrorBanner`, `Skeleton`.
- Produces:
  - `BookingCreateDialog({ open, onOpenChange, defaultBranchId, defaultDate, onCreated })`.
  - La agenda muestra "Nueva reserva" solo con `bookings.write` u `bookings.own.write`.

- [ ] **Step 1: Escribir las pruebas del alta de reserva**

`web/src/features/agenda/BookingCreateDialog.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test, vi } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { BookingCreateDialog } from './BookingCreateDialog';

const bookingFixture = {
  id: 'booking-9',
  company: 'company-a',
  branch: 'branch-1',
  branch_name: 'Providencia',
  customer: 'customer-1',
  customer_name: 'Ana Díaz',
  customer_email: 'ana@example.com',
  service: 'service-1',
  service_name: 'Corte de cabello',
  worker: 'worker-1',
  worker_name: 'Paula Rojas',
  start_at: '2026-11-12T13:00:00Z',
  end_at: '2026-11-12T13:30:00Z',
  duration_minutes: 30,
  price: '12000.00',
  status: 'scheduled',
  status_display: 'Agendada',
  source: 'staff',
  source_display: 'Equipo',
  notes: '',
  public_code: 'ABCDEFGHIJ',
  canceled_at: null,
  canceled_reason: '',
  created_at: '2026-11-11T12:00:00Z',
  updated_at: '2026-11-11T12:00:00Z',
};

const baseHandlers = [
  http.get('http://api.test/api/v1/services/', () =>
    HttpResponse.json({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 'service-1',
          company: 'company-a',
          name: 'Corte de cabello',
          description: '',
          duration_minutes: 30,
          price: '12000.00',
          buffer_before_minutes: 0,
          buffer_after_minutes: 0,
          branches: ['branch-1'],
          active: true,
          created_at: '2026-11-11T12:00:00Z',
          updated_at: '2026-11-11T12:00:00Z',
        },
      ],
    }),
  ),
  http.get('http://api.test/api/v1/workers/', () =>
    HttpResponse.json({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 'worker-1',
          company: 'company-a',
          membership: null,
          first_name: 'Paula',
          last_name: 'Rojas',
          display_name: 'Paula Rojas',
          email: '',
          phone: '',
          job_title: 'Estilista',
          color: '#10b981',
          branches: ['branch-1'],
          active: true,
          created_at: '2026-11-11T12:00:00Z',
          updated_at: '2026-11-11T12:00:00Z',
        },
      ],
    }),
  ),
  http.get('http://api.test/api/v1/customers/', () =>
    HttpResponse.json({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 'customer-1',
          company: 'company-a',
          first_name: 'Ana',
          last_name: 'Díaz',
          display_name: 'Ana Díaz',
          email: 'ana@example.com',
          phone: '',
          document_id: '',
          notes: '',
          active: true,
          created_at: '2026-11-11T12:00:00Z',
          updated_at: '2026-11-11T12:00:00Z',
        },
      ],
    }),
  ),
  http.get('http://api.test/api/v1/bookings/availability/', () =>
    HttpResponse.json({
      date: '2026-11-12',
      timezone: 'America/Santiago',
      slots: [
        { start_at: '2026-11-12T13:00:00Z', end_at: '2026-11-12T13:30:00Z', label: '10:00' },
        { start_at: '2026-11-12T13:30:00Z', end_at: '2026-11-12T14:00:00Z', label: '10:30' },
      ],
    }),
  ),
];

function renderDialog(open = true) {
  const onCreated = vi.fn();
  const onOpenChange = vi.fn();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <BookingCreateDialog
          open={open}
          onOpenChange={onOpenChange}
          defaultBranchId="branch-1"
          defaultDate="2026-11-12"
          onCreated={onCreated}
        />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
  return { onCreated, onOpenChange, queryClient };
}

async function chooseServiceWorkerAndSlot() {
  await screen.findByRole('option', { name: 'Corte de cabello · 30 min' });
  await userEvent.selectOptions(screen.getByLabelText('Servicio'), 'service-1');
  await screen.findByRole('option', { name: 'Paula Rojas' });
  await userEvent.selectOptions(screen.getByLabelText('Trabajador'), 'worker-1');
  await userEvent.click(await screen.findByRole('button', { name: '10:00' }));
}

describe('BookingCreateDialog', () => {
  test('crea la reserva con un cliente existente y un cupo disponible', async () => {
    let created: unknown;
    server.use(
      ...baseHandlers,
      http.post('http://api.test/api/v1/bookings/', async ({ request }) => {
        created = await request.json();
        return HttpResponse.json(bookingFixture, { status: 201 });
      }),
    );
    const { onCreated, onOpenChange } = renderDialog();

    await chooseServiceWorkerAndSlot();
    await screen.findByRole('option', { name: /Ana Díaz/ });
    await userEvent.selectOptions(screen.getByLabelText('Cliente'), 'customer-1');
    await userEvent.click(screen.getByRole('button', { name: 'Crear reserva' }));

    await waitFor(() =>
      expect(created).toMatchObject({
        branch: 'branch-1',
        service: 'service-1',
        worker: 'worker-1',
        customer: 'customer-1',
        start_at: '2026-11-12T13:00:00Z',
      }),
    );
    expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: 'booking-9' }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  test('un 409 conserva el diálogo y muestra el mensaje del servidor', async () => {
    server.use(
      ...baseHandlers,
      http.post('http://api.test/api/v1/bookings/', () =>
        HttpResponse.json(
          { detail: 'El horario seleccionado ya no está disponible.' },
          { status: 409 },
        ),
      ),
    );
    const { onCreated, onOpenChange } = renderDialog();

    await chooseServiceWorkerAndSlot();
    await screen.findByRole('option', { name: /Ana Díaz/ });
    await userEvent.selectOptions(screen.getByLabelText('Cliente'), 'customer-1');
    await userEvent.click(screen.getByRole('button', { name: 'Crear reserva' }));

    expect(
      await screen.findByText('El horario seleccionado ya no está disponible.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  test('crea un cliente nuevo antes de la reserva', async () => {
    const calls: string[] = [];
    let bookingBody: unknown;
    server.use(
      ...baseHandlers,
      http.post('http://api.test/api/v1/customers/', async ({ request }) => {
        calls.push('customer');
        const body = await request.json();
        return HttpResponse.json({ id: 'customer-new', ...(body as object) }, { status: 201 });
      }),
      http.post('http://api.test/api/v1/bookings/', async ({ request }) => {
        calls.push('booking');
        bookingBody = await request.json();
        return HttpResponse.json({ ...bookingFixture, customer: 'customer-new' }, { status: 201 });
      }),
    );
    renderDialog();

    await chooseServiceWorkerAndSlot();
    await userEvent.click(screen.getByRole('button', { name: 'Nuevo cliente' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Carla');
    await userEvent.type(screen.getByLabelText('Correo del cliente'), 'carla@example.com');
    await userEvent.click(screen.getByRole('button', { name: 'Crear reserva' }));

    await waitFor(() => expect(calls).toEqual(['customer', 'booking']));
    expect(bookingBody).toMatchObject({ customer: 'customer-new' });
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

Run: `cd web && npm run test -- src/features/agenda/BookingCreateDialog.test.tsx`

Expected: FAIL porque el diálogo no existe.

- [ ] **Step 3: Implementar el diálogo de alta**

`web/src/features/agenda/BookingCreateDialog.tsx`:

```tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import type { Booking } from '../../api/agenda';
import { agendaApi, customersApi, servicesApi, teamApi } from '../../api/runtime';
import { ApiError } from '../../api/client';
import { queryKeys } from '../../api/queryKeys';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select, Textarea } from '../../components/ui/Field';
import { Skeleton } from '../../components/ui/Skeleton';
import { useDebouncedValue } from '../../lib/useDebouncedValue';

const schema = z
  .object({
    branch: z.string().min(1, 'Selecciona una sucursal.'),
    service: z.string().min(1, 'Selecciona un servicio.'),
    worker: z.string().min(1, 'Selecciona un trabajador.'),
    date: z.string().min(1, 'Selecciona un día.'),
    notes: z.string().max(2000, 'Máximo 2000 caracteres.'),
    customerMode: z.enum(['existing', 'new']),
    customerId: z.string(),
    first_name: z.string(),
    last_name: z.string(),
    email: z.union([z.literal(''), z.string().email('Ingresa un correo válido.')]),
    phone: z.string(),
  })
  .superRefine((values, context) => {
    if (values.customerMode === 'existing' && !values.customerId) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['customerId'],
        message: 'Selecciona un cliente.',
      });
    }
    if (values.customerMode === 'new' && !values.first_name.trim()) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['first_name'],
        message: 'Ingresa el nombre del cliente.',
      });
    }
  });

type FormValues = z.infer<typeof schema>;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultBranchId: string;
  defaultDate: string;
  onCreated: (booking: Booking) => void;
};

export function BookingCreateDialog({
  open,
  onOpenChange,
  defaultBranchId,
  defaultDate,
  onCreated,
}: Props) {
  const { company, bootstrap } = useAuth();
  const queryClient = useQueryClient();
  const companyId = company?.id ?? '';
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);
  const [slot, setSlot] = useState<string | null>(null);
  const [customerSearch, setCustomerSearch] = useState('');
  const [banner, setBanner] = useState<string | null>(null);
  const [creatingCustomer, setCreatingCustomer] = useState(false);
  const search = useDebouncedValue(customerSearch, 300);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    setError,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      branch: defaultBranchId,
      service: '',
      worker: '',
      date: defaultDate,
      notes: '',
      customerMode: 'existing',
      customerId: '',
      first_name: '',
      last_name: '',
      email: '',
      phone: '',
    },
  });

  const branch = watch('branch');
  const service = watch('service');
  const worker = watch('worker');
  const date = watch('date');
  const customerMode = watch('customerMode');

  useEffect(() => {
    if (!open) return;
    reset({
      branch: defaultBranchId,
      service: '',
      worker: '',
      date: defaultDate,
      notes: '',
      customerMode: 'existing',
      customerId: '',
      first_name: '',
      last_name: '',
      email: '',
      phone: '',
    });
    setSlot(null);
    setCustomerSearch('');
    setBanner(null);
  }, [defaultBranchId, defaultDate, open, reset]);

  useEffect(() => {
    setSlot(null);
  }, [branch, date, service, worker]);

  const servicesQuery = useQuery({
    queryKey: queryKeys.services(companyId, { active: true }),
    queryFn: () => servicesApi.list({ active: true, page: 1 }),
    enabled: open && Boolean(companyId && branch),
  });
  const workersQuery = useQuery({
    queryKey: queryKeys.workers(companyId, { branch, active: true }),
    queryFn: () => teamApi.workers.list({ branch, active: true, page: 1 }),
    enabled: open && Boolean(companyId && branch),
  });
  const customersQuery = useQuery({
    queryKey: queryKeys.customers(companyId, { search, active: true, page: 1 }),
    queryFn: () => customersApi.list({ search, active: true, page: 1 }),
    enabled: open && customerMode === 'existing' && Boolean(companyId),
  });
  const availabilityQuery = useQuery({
    queryKey: queryKeys.availability(companyId, { branch, service, worker, date }),
    queryFn: () => agendaApi.availability({ branch, service, worker, date }),
    enabled: open && Boolean(companyId && branch && service && worker && date),
  });

  async function submit(values: FormValues) {
    setBanner(null);
    if (!slot) {
      setBanner('Selecciona un horario disponible.');
      return;
    }
    let customerId = values.customerId;
    try {
      if (values.customerMode === 'new') {
        setCreatingCustomer(true);
        const customer = await customersApi.create({
          first_name: values.first_name.trim(),
          last_name: values.last_name.trim(),
          email: values.email.trim(),
          phone: values.phone.trim(),
        });
        customerId = customer.id;
        setValue('customerMode', 'existing');
        setValue('customerId', customer.id);
      }
      const booking = await agendaApi.createBooking({
        branch: values.branch,
        customer: customerId,
        service: values.service,
        worker: values.worker,
        start_at: slot,
        notes: values.notes.trim(),
      });
      await queryClient.invalidateQueries({ queryKey: ['bookings', companyId] });
      await queryClient.invalidateQueries({ queryKey: ['availability', companyId] });
      onCreated(booking);
      onOpenChange(false);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setSlot(null);
        setBanner(error.message);
        void availabilityQuery.refetch();
        return;
      }
      if (error instanceof ApiError) {
        Object.entries(error.fields ?? {}).forEach(([field, messages]) => {
          if (field in values) {
            setError(field as keyof FormValues, { message: messages[0] });
          }
        });
        setBanner(error.message);
      } else {
        setBanner('No se pudo crear la reserva.');
      }
    } finally {
      setCreatingCustomer(false);
    }
  }

  const busy = isSubmitting || creatingCustomer;

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Nueva reserva"
      description="Solo se ofrecen cupos libres según horarios, pausas, ausencias y buffers."
      wide
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" form="booking-create-form" loading={busy} loadingLabel="Creando…">
            Crear reserva
          </Button>
        </>
      }
    >
      <form id="booking-create-form" className="space-y-4" onSubmit={handleSubmit(submit)} noValidate>
        {banner ? <ErrorBanner message={banner} /> : null}
        {servicesQuery.isError || workersQuery.isError ? (
          <ErrorBanner
            message="No se pudieron cargar los servicios o trabajadores."
            onRetry={() => {
              void servicesQuery.refetch();
              void workersQuery.refetch();
            }}
          />
        ) : null}
        {customersQuery.isError ? (
          <ErrorBanner
            message="No se pudieron cargar los clientes."
            onRetry={() => void customersQuery.refetch()}
          />
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Sucursal" htmlFor="booking-branch" error={errors.branch?.message}>
            <Select id="booking-branch" {...register('branch')}>
              {branches.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Día" htmlFor="booking-date" error={errors.date?.message}>
            <Input id="booking-date" type="date" {...register('date')} />
          </Field>

          <Field label="Servicio" htmlFor="booking-service" error={errors.service?.message}>
            <Select id="booking-service" {...register('service')}>
              <option value="">Selecciona un servicio</option>
              {(servicesQuery.data?.results ?? [])
                .filter(
                  (item) => item.branches.length === 0 || item.branches.includes(branch),
                )
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {item.duration_minutes} min
                  </option>
                ))}
            </Select>
          </Field>

          <Field label="Trabajador" htmlFor="booking-worker" error={errors.worker?.message}>
            <Select id="booking-worker" {...register('worker')}>
              <option value="">Selecciona un trabajador</option>
              {(workersQuery.data?.results ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.display_name}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <fieldset>
          <legend className="mb-2 text-sm font-medium text-ink">Horario disponible</legend>
          {!branch || !service || !worker || !date ? (
            <p className="text-sm text-muted">Elige sucursal, servicio, trabajador y día.</p>
          ) : availabilityQuery.isLoading ? (
            <Skeleton rows={2} />
          ) : availabilityQuery.isError ? (
            <ErrorBanner
              message={
                availabilityQuery.error instanceof Error
                  ? availabilityQuery.error.message
                  : 'No se pudo consultar la disponibilidad.'
              }
              onRetry={() => void availabilityQuery.refetch()}
            />
          ) : (availabilityQuery.data?.slots.length ?? 0) === 0 ? (
            <p className="text-sm text-muted">No hay cupos disponibles para ese día.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {availabilityQuery.data?.slots.map((item) => (
                <button
                  key={item.start_at}
                  type="button"
                  aria-pressed={slot === item.start_at}
                  onClick={() => setSlot(item.start_at)}
                  className={`rounded-md border px-3 py-1.5 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand ${
                    slot === item.start_at
                      ? 'border-brand bg-brand-soft text-brand'
                      : 'border-line bg-panel text-ink hover:bg-surface'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </fieldset>

        <fieldset className="space-y-3">
          <legend className="mb-2 text-sm font-medium text-ink">Cliente</legend>
          <div className="flex gap-2">
            <Button
              type="button"
              variant={customerMode === 'existing' ? 'primary' : 'secondary'}
              onClick={() => setValue('customerMode', 'existing')}
            >
              Cliente existente
            </Button>
            <Button
              type="button"
              variant={customerMode === 'new' ? 'primary' : 'secondary'}
              onClick={() => setValue('customerMode', 'new')}
            >
              Nuevo cliente
            </Button>
          </div>

          {customerMode === 'existing' ? (
            <div className="space-y-3">
              <Field label="Buscar cliente" htmlFor="booking-customer-search">
                <Input
                  id="booking-customer-search"
                  value={customerSearch}
                  onChange={(event) => setCustomerSearch(event.target.value)}
                  placeholder="Nombre, correo, teléfono o documento"
                />
              </Field>
              <Field label="Cliente" htmlFor="booking-customer" error={errors.customerId?.message}>
                <Select id="booking-customer" {...register('customerId')}>
                  <option value="">Selecciona un cliente</option>
                  {(customersQuery.data?.results ?? []).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.display_name}
                      {item.email ? ` · ${item.email}` : ''}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Nombre" htmlFor="booking-first-name" error={errors.first_name?.message}>
                <Input id="booking-first-name" {...register('first_name')} />
              </Field>
              <Field label="Apellido" htmlFor="booking-last-name">
                <Input id="booking-last-name" {...register('last_name')} />
              </Field>
              <Field label="Correo del cliente" htmlFor="booking-email" error={errors.email?.message}>
                <Input id="booking-email" type="email" {...register('email')} />
              </Field>
              <Field label="Teléfono" htmlFor="booking-phone">
                <Input id="booking-phone" {...register('phone')} />
              </Field>
            </div>
          )}
        </fieldset>

        <Field label="Notas" htmlFor="booking-notes" error={errors.notes?.message}>
          <Textarea id="booking-notes" rows={2} {...register('notes')} />
        </Field>
      </form>
    </Dialog>
  );
}
```

- [ ] **Step 4: Conectar el alta con la agenda**

En `web/src/features/agenda/AgendaPage.tsx`:

1. Importar `useQueryClient` y el diálogo:

```tsx
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { BookingCreateDialog } from './BookingCreateDialog';
```

2. Dentro del componente, agrega el cliente de consultas y el estado del diálogo, y reemplaza la línea existente `const { company, bootstrap } = useAuth();` por la versión con `can` (no declares un segundo `useAuth`):

```tsx
const queryClient = useQueryClient();
const [createOpen, setCreateOpen] = useState(false);
const { company, bootstrap, can } = useAuth();
```

3. Agregar la acción al `PageHeader`:

```tsx
<PageHeader
  title="Agenda"
  description={`Horarios en ${timezone} · ${periodLabel}`}
  actions={
    can('bookings.write') && can('customers.read') ? (
      <Button onClick={() => setCreateOpen(true)}>Nueva reserva</Button>
    ) : null
  }
/>
```

4. Renderizar el diálogo antes del detalle:

```tsx
<BookingCreateDialog
  open={createOpen}
  onOpenChange={setCreateOpen}
  defaultBranchId={branchId}
  defaultDate={anchorDate}
  onCreated={() => {
    void queryClient.invalidateQueries({ queryKey: ['bookings', company?.id] });
    setCreateOpen(false);
  }}
/>
```

`queryClient` no se usa en otro lugar del componente; si el lint lo marca como no usado por la invalidación del diálogo, la invalidación del padre lo usa.

- [ ] **Step 5: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test -- src/features/agenda
npm run build
npm run lint
```

Expected: 9 tests PASS; build y lint sin errores.

- [ ] **Step 6: Validación visual**

Con el backend local:

- Abrir "Nueva reserva", elegir sucursal, servicio, trabajador y día.
- Verificar que los cupos cambian al cambiar de día o trabajador.
- Crear un cliente nuevo y una reserva; el diálogo se cierra y la agenda se actualiza.
- Provocar un conflicto (crear dos veces el mismo cupo en otra pestaña) y comprobar que el mensaje queda visible con el formulario abierto.

- [ ] **Step 7: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/features/agenda
git commit -m "feat(web): add booking creation with live availability and inline customer"
```

---

### Task 12: Detalle con transiciones, notas y reprogramación

**Files:**
- Modify: `web/src/features/agenda/BookingDetailDialog.tsx`, `web/src/features/agenda/AgendaPage.tsx`
- Create: `web/src/features/agenda/BookingDetailDialog.test.tsx`

**Interfaces:**
- Consumes: `agendaApi`, `teamApi`, `queryKeys`, `formatDateTime`, `formatDateISO`, `formatTime`, `ConfirmDialog` no se usa.
- Produces:
  - `BookingDetailDialog({ booking, timezone, canWrite, onClose, onChanged })` con confirmar, completar, no-show, cancelar con motivo, reprogramar y guardar notas.
  - `AgendaPage` pasa `canWrite` y actualiza la reserva seleccionada al cambiar.

- [ ] **Step 1: Escribir las pruebas del detalle**

`web/src/features/agenda/BookingDetailDialog.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { useState } from 'react';
import { describe, expect, test, vi } from 'vitest';

import type { Booking } from '../../api/agenda';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { BookingDetailDialog } from './BookingDetailDialog';

const baseBooking: Booking = {
  id: 'booking-1',
  company: 'company-a',
  branch: 'branch-1',
  branch_name: 'Providencia',
  customer: 'customer-1',
  customer_name: 'Ana Díaz',
  customer_email: 'ana@example.com',
  service: 'service-1',
  service_name: 'Corte de cabello',
  worker: 'worker-1',
  worker_name: 'Paula Rojas',
  start_at: '2026-11-12T13:00:00Z',
  end_at: '2026-11-12T13:30:00Z',
  duration_minutes: 30,
  price: '12000.00',
  status: 'scheduled',
  status_display: 'Agendada',
  source: 'staff',
  source_display: 'Equipo',
  notes: '',
  public_code: 'ABCDEFGHIJ',
  canceled_at: null,
  canceled_reason: '',
  created_at: '2026-11-11T12:00:00Z',
  updated_at: '2026-11-11T12:00:00Z',
};

function Harness({
  initial = baseBooking,
  canWrite = true,
}: {
  initial?: Booking;
  canWrite?: boolean;
}) {
  const [booking, setBooking] = useState<Booking | null>(initial);
  return (
    <BookingDetailDialog
      booking={booking}
      timezone="America/Santiago"
      canWrite={canWrite}
      onClose={() => setBooking(null)}
      onChanged={(updated) => setBooking(updated)}
    />
  );
}

function renderDetail(options: { initial?: Booking; canWrite?: boolean } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <Harness {...options} />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

describe('BookingDetailDialog', () => {
  test('confirma la reserva y refleja el nuevo estado', async () => {
    server.use(
      http.post('http://api.test/api/v1/bookings/booking-1/confirm/', () =>
        HttpResponse.json({ ...baseBooking, status: 'confirmed', status_display: 'Confirmada' }),
      ),
    );
    renderDetail();

    await userEvent.click(screen.getByRole('button', { name: 'Confirmar' }));

    expect(await screen.findByText('Confirmada')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Confirmar' })).not.toBeInTheDocument();
  });

  test('muestra el conflicto al reprogramar', async () => {
    server.use(
      http.get('http://api.test/api/v1/workers/', () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 'worker-1',
              company: 'company-a',
              membership: null,
              first_name: 'Paula',
              last_name: 'Rojas',
              display_name: 'Paula Rojas',
              email: '',
              phone: '',
              job_title: 'Estilista',
              color: '#10b981',
              branches: ['branch-1'],
              active: true,
              created_at: '2026-11-11T12:00:00Z',
              updated_at: '2026-11-11T12:00:00Z',
            },
          ],
        }),
      ),
      http.get('http://api.test/api/v1/bookings/availability/', () =>
        HttpResponse.json({
          date: '2026-11-12',
          timezone: 'America/Santiago',
          slots: [
            { start_at: '2026-11-12T13:30:00Z', end_at: '2026-11-12T14:00:00Z', label: '10:30' },
          ],
        }),
      ),
      http.post('http://api.test/api/v1/bookings/booking-1/reschedule/', () =>
        HttpResponse.json(
          { detail: 'El horario seleccionado ya no está disponible.' },
          { status: 409 },
        ),
      ),
    );
    renderDetail();

    await userEvent.click(screen.getByRole('button', { name: 'Reprogramar' }));
    await userEvent.click(await screen.findByRole('button', { name: '10:30' }));
    await userEvent.click(screen.getByRole('button', { name: 'Reprogramar reserva' }));

    expect(
      await screen.findByText('El horario seleccionado ya no está disponible.'),
    ).toBeInTheDocument();
  });

  test('guarda las notas con PATCH', async () => {
    let body: unknown;
    server.use(
      http.patch('http://api.test/api/v1/bookings/booking-1/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...baseBooking, notes: 'Llegó antes' });
      }),
    );
    renderDetail();

    await userEvent.type(screen.getByLabelText('Notas'), 'Llegó antes');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar notas' }));

    await waitFor(() => expect(body).toEqual({ notes: 'Llegó antes' }));
  });

  test('sin permiso de escritura no muestra acciones', () => {
    renderDetail({ canWrite: false });
    expect(screen.queryByRole('button', { name: 'Confirmar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reprogramar' })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

Run: `cd web && npm run test -- src/features/agenda/BookingDetailDialog.test.tsx`

Expected: FAIL porque faltan las acciones.

- [ ] **Step 3: Implementar el detalle completo**

`web/src/features/agenda/BookingDetailDialog.tsx`:

```tsx
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import type { Booking, BookingAction } from '../../api/agenda';
import { agendaApi, teamApi } from '../../api/runtime';
import { ApiError } from '../../api/client';
import { queryKeys } from '../../api/queryKeys';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select, Textarea } from '../../components/ui/Field';
import { formatDateISO, formatDateTime } from '../../lib/dates';
import { BOOKING_STATUS_LABELS, formatMoney } from '../../lib/format';

type Props = {
  booking: Booking | null;
  timezone: string;
  canWrite: boolean;
  onClose: () => void;
  onChanged: (booking: Booking) => void;
};

const ACTIVE_STATUSES = ['scheduled', 'confirmed'];

function messageOf(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

export function BookingDetailDialog({ booking, timezone, canWrite, onClose, onChanged }: Props) {
  const { company } = useAuth();
  const companyId = company?.id ?? '';
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [cancelMode, setCancelMode] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [rescheduleOpen, setRescheduleOpen] = useState(false);
  const [rescheduleDate, setRescheduleDate] = useState('');
  const [rescheduleWorker, setRescheduleWorker] = useState('');
  const [rescheduleReason, setRescheduleReason] = useState('');
  const [rescheduleSlot, setRescheduleSlot] = useState<string | null>(null);
  const [rescheduleError, setRescheduleError] = useState<string | null>(null);

  useEffect(() => {
    if (!booking) return;
    setNotes(booking.notes);
    setActionError(null);
    setCancelMode(false);
    setCancelReason('');
    setRescheduleOpen(false);
    setRescheduleDate(formatDateISO(booking.start_at, timezone));
    setRescheduleWorker(booking.worker);
    setRescheduleReason('');
    setRescheduleSlot(null);
    setRescheduleError(null);
  }, [booking, timezone]);

  const workersQuery = useQuery({
    queryKey: queryKeys.workers(companyId, { branch: booking?.branch, active: true }),
    queryFn: () => teamApi.workers.list({ branch: booking?.branch, active: true, page: 1 }),
    enabled: Boolean(booking && rescheduleOpen && companyId),
  });

  const availabilityQuery = useQuery({
    queryKey: queryKeys.availability(companyId, {
      branch: booking?.branch ?? '',
      service: booking?.service ?? '',
      worker: rescheduleWorker,
      date: rescheduleDate,
    }),
    queryFn: () =>
      agendaApi.availability({
        branch: booking?.branch ?? '',
        service: booking?.service ?? '',
        worker: rescheduleWorker,
        date: rescheduleDate,
      }),
    enabled: Boolean(booking && rescheduleOpen && companyId && rescheduleDate && rescheduleWorker),
  });

  if (!booking) return null;

  const active = ACTIVE_STATUSES.includes(booking.status);
  const editable = canWrite && active;

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ['bookings', companyId] });
    void queryClient.invalidateQueries({ queryKey: ['availability', companyId] });
  }

  async function runAction(action: BookingAction, reason = '') {
    setBusyAction(action);
    setActionError(null);
    try {
      const updated = await agendaApi.transitionBooking(booking!.id, action, reason);
      invalidate();
      onChanged(updated);
      setCancelMode(false);
      setCancelReason('');
    } catch (error) {
      setActionError(messageOf(error, 'No se pudo actualizar la reserva.'));
    } finally {
      setBusyAction(null);
    }
  }

  async function saveNotes() {
    setBusyAction('notes');
    setActionError(null);
    try {
      const updated = await agendaApi.updateNotes(booking!.id, notes);
      invalidate();
      onChanged(updated);
    } catch (error) {
      setActionError(messageOf(error, 'No se pudieron guardar las notas.'));
    } finally {
      setBusyAction(null);
    }
  }

  async function reschedule() {
    if (!rescheduleSlot) {
      setRescheduleError('Selecciona un horario disponible.');
      return;
    }
    setBusyAction('reschedule');
    setRescheduleError(null);
    try {
      const updated = await agendaApi.rescheduleBooking(booking!.id, {
        start_at: rescheduleSlot,
        worker: rescheduleWorker,
        reason: rescheduleReason.trim(),
      });
      invalidate();
      onChanged(updated);
      setRescheduleOpen(false);
      setRescheduleSlot(null);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setRescheduleSlot(null);
        setRescheduleError(error.message);
        void availabilityQuery.refetch();
        return;
      }
      setRescheduleError(messageOf(error, 'No se pudo reprogramar la reserva.'));
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Detalle de reserva"
      description={`${booking.service_name} · ${booking.customer_name}`}
      wide
      footer={
        <Button variant="secondary" onClick={onClose}>
          Cerrar
        </Button>
      }
    >
      {actionError ? <ErrorBanner message={actionError} /> : null}

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-muted">Inicio</dt>
          <dd className="text-ink">{formatDateTime(booking.start_at, timezone)}</dd>
        </div>
        <div>
          <dt className="text-muted">Fin</dt>
          <dd className="text-ink">{formatDateTime(booking.end_at, timezone)}</dd>
        </div>
        <div>
          <dt className="text-muted">Trabajador</dt>
          <dd className="text-ink">{booking.worker_name}</dd>
        </div>
        <div>
          <dt className="text-muted">Sucursal</dt>
          <dd className="text-ink">{booking.branch_name}</dd>
        </div>
        <div>
          <dt className="text-muted">Precio</dt>
          <dd className="text-ink">{formatMoney(booking.price)}</dd>
        </div>
        <div>
          <dt className="text-muted">Estado</dt>
          <dd>
            <Badge tone={booking.status}>{BOOKING_STATUS_LABELS[booking.status]}</Badge>
          </dd>
        </div>
      </dl>

      {canWrite ? (
        <div className="mt-4">
          <Field label="Notas" htmlFor="booking-detail-notes">
            <Textarea
              id="booking-detail-notes"
              rows={2}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </Field>
          <Button
            className="mt-2"
            variant="secondary"
            loading={busyAction === 'notes'}
            loadingLabel="Guardando…"
            onClick={() => void saveNotes()}
          >
            Guardar notas
          </Button>
        </div>
      ) : (
        <p className="mt-4 text-sm text-ink">
          <span className="text-muted">Notas: </span>
          {booking.notes || 'Sin notas'}
        </p>
      )}

      {editable ? (
        <section className="mt-6 space-y-3 border-t border-line pt-4">
          <h3 className="text-sm font-semibold text-ink">Acciones</h3>
          <div className="flex flex-wrap gap-2">
            {booking.status === 'scheduled' ? (
              <Button
                loading={busyAction === 'confirm'}
                onClick={() => void runAction('confirm')}
              >
                Confirmar
              </Button>
            ) : null}
            <Button
              variant="secondary"
              loading={busyAction === 'complete'}
              onClick={() => void runAction('complete')}
            >
              Completar
            </Button>
            <Button
              variant="secondary"
              loading={busyAction === 'no-show'}
              onClick={() => void runAction('no-show')}
            >
              No asistió
            </Button>
            <Button variant="danger" onClick={() => setCancelMode((value) => !value)}>
              Cancelar reserva
            </Button>
            <Button variant="secondary" onClick={() => setRescheduleOpen((value) => !value)}>
              Reprogramar
            </Button>
          </div>

          {cancelMode ? (
            <div className="rounded-md border border-danger/40 bg-danger-soft/40 p-3">
              <Field label="Motivo de cancelación" htmlFor="booking-cancel-reason">
                <Input
                  id="booking-cancel-reason"
                  value={cancelReason}
                  onChange={(event) => setCancelReason(event.target.value)}
                />
              </Field>
              <Button
                className="mt-2"
                variant="danger"
                loading={busyAction === 'cancel'}
                onClick={() => void runAction('cancel', cancelReason)}
              >
                Confirmar cancelación
              </Button>
            </div>
          ) : null}

          {rescheduleOpen ? (
            <div className="rounded-md border border-line bg-surface p-3">
              {rescheduleError ? <ErrorBanner message={rescheduleError} /> : null}
              <div className="mt-2 grid gap-3 sm:grid-cols-2">
                <Field label="Nuevo día" htmlFor="booking-reschedule-date">
                  <Input
                    id="booking-reschedule-date"
                    type="date"
                    value={rescheduleDate}
                    onChange={(event) => {
                      setRescheduleDate(event.target.value);
                      setRescheduleSlot(null);
                    }}
                  />
                </Field>
                <Field label="Trabajador para reprogramar" htmlFor="booking-reschedule-worker">
                  <Select
                    id="booking-reschedule-worker"
                    value={rescheduleWorker}
                    onChange={(event) => {
                      setRescheduleWorker(event.target.value);
                      setRescheduleSlot(null);
                    }}
                  >
                    {(workersQuery.data?.results ?? []).length === 0 ? (
                      <option value={booking.worker}>{booking.worker_name}</option>
                    ) : (
                      (workersQuery.data?.results ?? []).map((worker) => (
                        <option key={worker.id} value={worker.id}>
                          {worker.display_name}
                        </option>
                      ))
                    )}
                  </Select>
                </Field>
                <Field label="Motivo de reprogramación" htmlFor="booking-reschedule-reason">
                  <Input
                    id="booking-reschedule-reason"
                    value={rescheduleReason}
                    onChange={(event) => setRescheduleReason(event.target.value)}
                  />
                </Field>
              </div>

              <div className="mt-3">
                {availabilityQuery.isError ? (
                  <ErrorBanner
                    message={
                      availabilityQuery.error instanceof Error
                        ? availabilityQuery.error.message
                        : 'No se pudo consultar la disponibilidad.'
                    }
                    onRetry={() => void availabilityQuery.refetch()}
                  />
                ) : availabilityQuery.isLoading ? (
                  <p className="text-sm text-muted">Consultando disponibilidad…</p>
                ) : (availabilityQuery.data?.slots.length ?? 0) === 0 ? (
                  <p className="text-sm text-muted">No hay cupos disponibles ese día.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {availabilityQuery.data?.slots.map((item) => (
                      <button
                        key={item.start_at}
                        type="button"
                        aria-pressed={rescheduleSlot === item.start_at}
                        onClick={() => setRescheduleSlot(item.start_at)}
                        className={`rounded-md border px-3 py-1.5 text-sm ${
                          rescheduleSlot === item.start_at
                            ? 'border-brand bg-brand-soft text-brand'
                            : 'border-line bg-panel text-ink'
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <Button
                className="mt-3"
                loading={busyAction === 'reschedule'}
                onClick={() => void reschedule()}
              >
                Reprogramar reserva
              </Button>
            </div>
          ) : null}
        </section>
      ) : null}
    </Dialog>
  );
}
```

- [ ] **Step 4: Actualizar la agenda**

En `web/src/features/agenda/AgendaPage.tsx`, reemplazar el detalle:

```tsx
<BookingDetailDialog
  booking={selected}
  timezone={timezone}
  canWrite={can('bookings.write')}
  onClose={() => setSelected(null)}
  onChanged={(updated) => {
    setSelected(updated);
    void queryClient.invalidateQueries({ queryKey: ['bookings', company?.id] });
    void queryClient.invalidateQueries({ queryKey: ['availability', company?.id] });
  }}
/>
```

Asegurar que el componente desestructura `can` desde `useAuth` (ver tarea 11).

- [ ] **Step 5: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test -- src/features/agenda
npm run build
npm run lint
```

Expected: 13 tests PASS; build y lint sin errores.

- [ ] **Step 6: Validación visual**

Con una reserva local:

- Confirmar, completar y marcar no-show; el badge cambia sin cerrar el diálogo.
- Cancelar con motivo; verificar en la agenda que la reserva queda cancelada.
- Reprogramar a otro cupo; el bloque se mueve en la agenda.
- Intentar un cupo ocupado y comprobar el mensaje 409.
- Repetir en claro y oscuro y con teclado.

- [ ] **Step 7: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/features/agenda
git commit -m "feat(web): add booking detail actions, notes and reschedule"
```

---

### Task 13: Clientes con búsqueda, alta, edición, historial y desactivación

**Files:**
- Create: `web/src/features/customers/CustomersPage.tsx`, `web/src/features/customers/CustomerFormDialog.tsx`, `web/src/features/customers/CustomerHistoryDialog.tsx`, `web/src/features/customers/CustomersPage.test.tsx`
- Modify: `web/src/app/router.tsx`

**Interfaces:**
- Consumes: `customersApi`, `agendaApi`, `queryKeys`, `useAuth`, `useDebouncedValue`, `ApiError`, `Button`, `Badge`, `Dialog`, `ConfirmDialog`, `Field`, `FormRow`, `Input`, `Select`, `Textarea`, `EmptyState`, `ErrorBanner`, `PageHeader`, `Pagination`, `Skeleton`, `formatDateTime`.
- Produces:
  - `CustomersPage` con búsqueda por texto, filtro de estado, tabla, paginación, alta/edición, historial y activación/desactivación.
  - `CustomerFormDialog({ open, customer, onOpenChange, onSaved })`: `customer` nulo crea, con cliente edita.
  - `CustomerHistoryDialog({ customer, onClose })`: últimas 50 reservas del cliente ordenadas por fecha descendente.

- [ ] **Step 1: Escribir las pruebas de clientes**

`web/src/features/customers/CustomersPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import type { Customer } from '../../api/customers';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { CustomersPage } from './CustomersPage';

const ana: Customer = {
  id: 'customer-1',
  company: 'company-a',
  first_name: 'Ana',
  last_name: 'Díaz',
  display_name: 'Ana Díaz',
  email: 'ana@example.com',
  phone: '+56911111111',
  document_id: '11111111-1',
  notes: '',
  active: true,
  created_at: '2026-11-01T12:00:00Z',
  updated_at: '2026-11-01T12:00:00Z',
};

const beatriz: Customer = {
  ...ana,
  id: 'customer-2',
  first_name: 'Beatriz',
  last_name: 'Soto',
  display_name: 'Beatriz Soto',
  email: 'beatriz@example.com',
  document_id: '',
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <CustomersPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function listHandler(customers: () => Customer[]) {
  return http.get('http://api.test/api/v1/customers/', () => {
    const results = customers();
    return HttpResponse.json({
      count: results.length,
      next: null,
      previous: null,
      results,
    });
  });
}

describe('CustomersPage', () => {
  test('lista y busca clientes por texto', async () => {
    const urls: string[] = [];
    server.use(
      http.get('http://api.test/api/v1/customers/', ({ request }) => {
        const url = new URL(request.url);
        urls.push(url.toString());
        const search = (url.searchParams.get('search') ?? '').toLowerCase();
        const results = [ana, beatriz].filter((item) =>
          item.display_name.toLowerCase().includes(search),
        );
        return HttpResponse.json({ count: results.length, next: null, previous: null, results });
      }),
    );
    renderPage();

    expect(await screen.findByText(/Ana Díaz/)).toBeInTheDocument();
    expect(screen.getByText('Beatriz Soto')).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('Buscar'), 'beatriz');

    await waitFor(() => expect(screen.queryByText('Ana Díaz')).not.toBeInTheDocument());
    expect(await screen.findByText('Beatriz Soto')).toBeInTheDocument();
    expect(urls.some((url) => url.includes('search=beatriz'))).toBe(true);
  });

  test('crea un cliente con los datos del formulario', async () => {
    let customers = [ana];
    let body: unknown;
    server.use(
      listHandler(() => customers),
      http.post('http://api.test/api/v1/customers/', async ({ request }) => {
        body = await request.json();
        const created: Customer = {
          ...ana,
          id: 'customer-3',
          first_name: 'Carla',
          last_name: 'Muñoz',
          display_name: 'Carla Muñoz',
          email: 'carla@example.com',
          phone: '',
          document_id: '',
        };
        customers = [created, ...customers];
        return HttpResponse.json(created, { status: 201 });
      }),
    );
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo cliente' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Carla');
    await userEvent.type(screen.getByLabelText('Apellido'), 'Muñoz');
    await userEvent.type(screen.getByLabelText('Correo'), 'carla@example.com');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cliente' }));

    await waitFor(() =>
      expect(body).toEqual({
        first_name: 'Carla',
        last_name: 'Muñoz',
        email: 'carla@example.com',
        phone: '',
        document_id: '',
        notes: '',
        active: true,
      }),
    );
    expect(await screen.findByText('Carla Muñoz')).toBeInTheDocument();
  });

  test('muestra el error por campo que devuelve el servidor', async () => {
    server.use(
      listHandler(() => [ana]),
      http.post('http://api.test/api/v1/customers/', () =>
        HttpResponse.json(
          { email: ['Ya existe un cliente con este correo.'] },
          { status: 400 },
        ),
      ),
    );
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo cliente' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Carla');
    await userEvent.type(screen.getByLabelText('Correo'), 'carla@example.com');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cliente' }));

    const dialog = await screen.findByRole('dialog');
    expect(
      await within(dialog).findAllByText('Ya existe un cliente con este correo.'),
    ).not.toHaveLength(0);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  test('desactiva un cliente tras confirmar', async () => {
    let customers = [ana];
    let body: unknown;
    server.use(
      listHandler(() => customers),
      http.patch('http://api.test/api/v1/customers/customer-1/', async ({ request }) => {
        body = await request.json();
        const updated = { ...ana, active: false };
        customers = [updated];
        return HttpResponse.json(updated);
      }),
    );
    renderPage();

    const row = await screen.findByRole('row', { name: /Ana Díaz/ });
    await userEvent.click(within(row).getByRole('button', { name: 'Desactivar' }));
    await userEvent.click(screen.getByRole('button', { name: 'Desactivar' }));

    await waitFor(() => expect(body).toEqual({ active: false }));
    expect(await screen.findByText('Inactivo')).toBeInTheDocument();
  });

  test('abre el historial de reservas del cliente', async () => {
    const bookingUrls: string[] = [];
    server.use(
      listHandler(() => [ana]),
      http.get('http://api.test/api/v1/bookings/', ({ request }) => {
        bookingUrls.push(request.url);
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 'booking-1',
              company: 'company-a',
              branch: 'branch-1',
              branch_name: 'Providencia',
              customer: 'customer-1',
              customer_name: 'Ana Díaz',
              customer_email: 'ana@example.com',
              service: 'service-1',
              service_name: 'Corte de cabello',
              worker: 'worker-1',
              worker_name: 'Paula Rojas',
              start_at: '2026-11-12T13:00:00Z',
              end_at: '2026-11-12T13:30:00Z',
              duration_minutes: 30,
              price: '12000.00',
              status: 'scheduled',
              status_display: 'Agendada',
              source: 'staff',
              source_display: 'Equipo',
              notes: '',
              public_code: 'ABCDEFGHIJ',
              canceled_at: null,
              canceled_reason: '',
              created_at: '2026-11-11T12:00:00Z',
              updated_at: '2026-11-11T12:00:00Z',
            },
          ],
        });
      }),
    );
    renderPage();

    const row = await screen.findByRole('row', { name: /Ana Díaz/ });
    await userEvent.click(within(row).getByRole('button', { name: 'Historial' }));

    expect(
      await screen.findByRole('heading', { name: 'Historial de Ana Díaz' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Corte de cabello')).toBeInTheDocument();
    expect(screen.getByText('Agendada')).toBeInTheDocument();
    expect(bookingUrls[0]).toContain('customer=customer-1');
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas para verificar que fallan**

Run: `cd web && npm run test -- src/features/customers/CustomersPage.test.tsx`

Expected: FAIL porque `CustomersPage` no existe.

- [ ] **Step 3: Implementar el formulario de cliente**

`web/src/features/customers/CustomerFormDialog.tsx`:

```tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import type { Customer, CustomerInput } from '../../api/customers';
import { customersApi } from '../../api/runtime';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Textarea } from '../../components/ui/Field';

const customerSchema = z.object({
  first_name: z.string().trim().min(2, 'Ingresa al menos 2 caracteres.'),
  last_name: z.string().trim().max(120, 'Máximo 120 caracteres.'),
  email: z
    .string()
    .trim()
    .refine(
      (value) => value === '' || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
      'Ingresa un correo válido.',
    ),
  phone: z.string().trim().max(32, 'Máximo 32 caracteres.'),
  document_id: z.string().trim().max(32, 'Máximo 32 caracteres.'),
  notes: z.string().max(2000, 'Máximo 2000 caracteres.'),
  active: z.boolean(),
});

type CustomerFormValues = z.infer<typeof customerSchema>;

const FIELD_NAMES = [
  'first_name',
  'last_name',
  'email',
  'phone',
  'document_id',
  'notes',
] as const;

function valuesFrom(customer: Customer | null): CustomerFormValues {
  return {
    first_name: customer?.first_name ?? '',
    last_name: customer?.last_name ?? '',
    email: customer?.email ?? '',
    phone: customer?.phone ?? '',
    document_id: customer?.document_id ?? '',
    notes: customer?.notes ?? '',
    active: customer?.active ?? true,
  };
}

export function CustomerFormDialog({
  open,
  customer,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  customer: Customer | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<CustomerFormValues>({
    resolver: zodResolver(customerSchema),
    defaultValues: valuesFrom(customer),
  });

  const mutation = useMutation({
    mutationFn: (values: CustomerInput) =>
      customer ? customersApi.update(customer.id, values) : customersApi.create(values),
    onSuccess: () => {
      onSaved();
      onOpenChange(false);
    },
    onError: (error) => {
      if (!(error instanceof ApiError) || !error.fields) return;
      Object.entries(error.fields).forEach(([field, messages]) => {
        if ((FIELD_NAMES as readonly string[]).includes(field)) {
          setError(field as (typeof FIELD_NAMES)[number], { message: messages[0] });
        }
      });
    },
  });

  const onSubmit = handleSubmit((values) => {
    mutation.mutate(values);
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onOpenChange(false);
      }}
      title={customer ? 'Editar cliente' : 'Nuevo cliente'}
      description="Los datos de contacto se usan para confirmar y recordar reservas."
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {mutation.error ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudo guardar el cliente.'
            }
          />
        ) : null}

        <FormRow>
          <Field label="Nombre" htmlFor="customer-first-name" error={errors.first_name?.message}>
            <Input id="customer-first-name" autoComplete="given-name" {...register('first_name')} />
          </Field>
          <Field label="Apellido" htmlFor="customer-last-name" error={errors.last_name?.message}>
            <Input id="customer-last-name" autoComplete="family-name" {...register('last_name')} />
          </Field>
        </FormRow>

        <FormRow>
          <Field label="Correo" htmlFor="customer-email" error={errors.email?.message}>
            <Input id="customer-email" type="email" autoComplete="email" {...register('email')} />
          </Field>
          <Field label="Teléfono" htmlFor="customer-phone" error={errors.phone?.message}>
            <Input id="customer-phone" type="tel" autoComplete="tel" {...register('phone')} />
          </Field>
        </FormRow>

        <Field label="Documento" htmlFor="customer-document" error={errors.document_id?.message}>
          <Input id="customer-document" {...register('document_id')} />
        </Field>

        <Field label="Notas" htmlFor="customer-notes" error={errors.notes?.message}>
          <Textarea id="customer-notes" rows={3} {...register('notes')} />
        </Field>

        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" className="h-4 w-4 accent-brand" {...register('active')} />
          Cliente activo
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending} loadingLabel="Guardando…">
            Guardar cliente
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
```

`web/src/features/customers/CustomerHistoryDialog.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query';

import type { Customer } from '../../api/customers';
import { agendaApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Dialog } from '../../components/ui/Dialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Skeleton } from '../../components/ui/Skeleton';
import { formatDateTime } from '../../lib/dates';

export function CustomerHistoryDialog({
  customer,
  onClose,
}: {
  customer: Customer;
  onClose: () => void;
}) {
  const { company, bootstrap } = useAuth();
  const query = useQuery({
    queryKey: queryKeys.customerBookings(company?.id ?? '', customer.id),
    queryFn: () =>
      agendaApi.listBookings({ customer: customer.id, ordering: '-start_at', page: 1 }),
    enabled: Boolean(company),
  });

  const timezoneFor = (branchId: string) =>
    bootstrap?.branches.find((branch) => branch.id === branchId)?.timezone ?? 'America/Santiago';

  const bookings = query.data?.results ?? [];

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={`Historial de ${customer.display_name}`}
      description="Últimas reservas registradas para este cliente."
      wide
    >
      {query.isPending ? <Skeleton rows={3} /> : null}
      {query.isError ? (
        <ErrorBanner
          message="No se pudo cargar el historial."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {query.isSuccess && bookings.length === 0 ? (
        <EmptyState
          title="Sin reservas"
          description="Este cliente todavía no tiene reservas registradas."
        />
      ) : null}
      {bookings.length > 0 ? (
        <>
          <ul className="divide-y divide-line">
            {bookings.map((booking) => (
              <li
                key={booking.id}
                className="flex flex-wrap items-center justify-between gap-2 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-ink">{booking.service_name}</p>
                  <p className="text-xs text-muted">
                    {formatDateTime(booking.start_at, timezoneFor(booking.branch))} ·{' '}
                    {booking.worker_name}
                  </p>
                </div>
                <Badge tone={booking.status}>{booking.status_display}</Badge>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-muted">
            {query.data && query.data.count > bookings.length
              ? `Se muestran las últimas ${bookings.length} de ${query.data.count} reservas.`
              : `${bookings.length} reservas en total.`}
          </p>
        </>
      ) : null}
    </Dialog>
  );
}
```

- [ ] **Step 4: Implementar la página de clientes**

`web/src/features/customers/CustomersPage.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError } from '../../api/client';
import type { Customer, CustomerListParams } from '../../api/customers';
import { customersApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/Dialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select } from '../../components/ui/Field';
import { PageHeader } from '../../components/ui/PageHeader';
import { Pagination } from '../../components/ui/Pagination';
import { Skeleton } from '../../components/ui/Skeleton';
import { useDebouncedValue } from '../../lib/useDebouncedValue';
import { CustomerFormDialog } from './CustomerFormDialog';
import { CustomerHistoryDialog } from './CustomerHistoryDialog';

export function CustomersPage() {
  const { company, can } = useAuth();
  const queryClient = useQueryClient();
  const canWrite = can('customers.write');

  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);
  const [activeFilter, setActiveFilter] = useState<'' | 'true' | 'false'>('');
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [history, setHistory] = useState<Customer | null>(null);
  const [pendingToggle, setPendingToggle] = useState<Customer | null>(null);

  const params: CustomerListParams = {
    search: debouncedSearch || undefined,
    active: activeFilter === '' ? undefined : activeFilter === 'true',
    page,
    ordering: 'last_name',
  };

  const query = useQuery({
    queryKey: queryKeys.customers(company?.id ?? '', params),
    queryFn: () => customersApi.list(params),
    enabled: Boolean(company),
  });

  const toggle = useMutation({
    mutationFn: (customer: Customer) => customersApi.setActive(customer.id, !customer.active),
    onSuccess: () => {
      setPendingToggle(null);
      void queryClient.invalidateQueries({ queryKey: ['customers', company?.id ?? ''] });
    },
  });

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(customer: Customer) {
    setEditing(customer);
    setFormOpen(true);
  }

  const customers = query.data?.results ?? [];
  const toggleError =
    toggle.error instanceof ApiError
      ? toggle.error.message
      : toggle.error
        ? 'No se pudo actualizar el cliente.'
        : null;

  return (
    <section>
      <PageHeader
        title="Clientes"
        description="Directorio de clientes de la empresa con su historial de reservas."
        actions={
          canWrite ? (
            <Button onClick={openCreate}>Nuevo cliente</Button>
          ) : null
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_12rem]">
        <Field label="Buscar" htmlFor="customer-search">
          <Input
            id="customer-search"
            type="search"
            placeholder="Nombre, correo, teléfono o documento"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </Field>
        <Field label="Estado" htmlFor="customer-active">
          <Select
            id="customer-active"
            value={activeFilter}
            onChange={(event) => {
              setActiveFilter(event.target.value as '' | 'true' | 'false');
              setPage(1);
            }}
          >
            <option value="">Todos</option>
            <option value="true">Activos</option>
            <option value="false">Inactivos</option>
          </Select>
        </Field>
      </div>

      {toggleError ? <ErrorBanner message={toggleError} /> : null}
      {query.isError ? (
        <ErrorBanner message="No se pudieron cargar los clientes." onRetry={() => void query.refetch()} />
      ) : null}
      {query.isPending ? <Skeleton rows={5} /> : null}

      {query.isSuccess && customers.length === 0 ? (
        <EmptyState
          title="Sin clientes"
          description={
            debouncedSearch || activeFilter
              ? 'No hay clientes que coincidan con los filtros.'
              : 'Crea el primer cliente para asociarlo a reservas.'
          }
          action={canWrite ? <Button onClick={openCreate}>Nuevo cliente</Button> : undefined}
        />
      ) : null}

      {customers.length > 0 ? (
        <>
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3">Cliente</th>
                  <th scope="col" className="px-4 py-3">Contacto</th>
                  <th scope="col" className="px-4 py-3">Documento</th>
                  <th scope="col" className="px-4 py-3">Estado</th>
                  <th scope="col" className="px-4 py-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {customers.map((customer) => (
                  <tr key={customer.id}>
                    <td className="px-4 py-3 font-medium text-ink">{customer.display_name}</td>
                    <td className="px-4 py-3 text-muted">
                      <span className="block">{customer.email || 'Sin correo'}</span>
                      <span className="block text-xs">{customer.phone || 'Sin teléfono'}</span>
                    </td>
                    <td className="px-4 py-3 text-muted">{customer.document_id || '—'}</td>
                    <td className="px-4 py-3">
                      <Badge tone={customer.active ? 'active' : 'inactive'}>
                        {customer.active ? 'Activo' : 'Inactivo'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap justify-end gap-1">
                        {can('bookings.read') ? (
                          <Button variant="ghost" onClick={() => setHistory(customer)}>
                            Historial
                          </Button>
                        ) : null}
                        {canWrite ? (
                          <>
                            <Button variant="ghost" onClick={() => openEdit(customer)}>
                              Editar
                            </Button>
                            <Button variant="ghost" onClick={() => setPendingToggle(customer)}>
                              {customer.active ? 'Desactivar' : 'Reactivar'}
                            </Button>
                          </>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} count={query.data?.count ?? 0} onPage={setPage} />
        </>
      ) : null}

      {formOpen ? (
        <CustomerFormDialog
          open
          customer={editing}
          onOpenChange={(next) => {
            if (!next) setFormOpen(false);
          }}
          onSaved={() => {
            void queryClient.invalidateQueries({ queryKey: ['customers', company?.id ?? ''] });
          }}
        />
      ) : null}

      {history ? (
        <CustomerHistoryDialog customer={history} onClose={() => setHistory(null)} />
      ) : null}

      <ConfirmDialog
        open={Boolean(pendingToggle)}
        onOpenChange={(next) => {
          if (!next) setPendingToggle(null);
        }}
        title={pendingToggle?.active ? 'Desactivar cliente' : 'Reactivar cliente'}
        description={
          pendingToggle
            ? `${pendingToggle.active ? 'El cliente dejará de aparecer' : 'El cliente volverá a aparecer'} en las búsquedas y nuevas reservas. Su historial se conserva.`
            : ''
        }
        confirmLabel={pendingToggle?.active ? 'Desactivar' : 'Reactivar'}
        danger={Boolean(pendingToggle?.active)}
        loading={toggle.isPending}
        onConfirm={() => {
          if (pendingToggle) toggle.mutate(pendingToggle);
        }}
      />
    </section>
  );
}
```

- [ ] **Step 5: Reemplazar la ruta de clientes**

En `web/src/app/router.tsx`, importar `CustomersPage` y reemplazar el placeholder:

```tsx
import { CustomersPage } from '../features/customers/CustomersPage';
```

```tsx
      {
        path: 'clientes',
        element: (
          <RequirePermission permission="customers.read">
            <CustomersPage />
          </RequirePermission>
        ),
      },
```

- [ ] **Step 6: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test -- src/features/customers
npm run build
npm run lint
```

Expected: 5 tests PASS; build y lint sin errores.

- [ ] **Step 7: Validación visual**

Con la empresa demo:

- Buscar por nombre y por correo; el filtro de estado combina con la búsqueda.
- Crear un cliente y verlo en la tabla sin recargar.
- Editar el mismo cliente y comprobar los valores precargados.
- Abrir el historial de un cliente con reservas y otro sin reservas.
- Desactivar y reactivar; el badge cambia y el cliente desaparece o reaparece según el filtro.
- Repetir en claro y oscuro, con teclado y a 768 px.

- [ ] **Step 8: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/features/customers web/src/app/router.tsx
git commit -m "feat(web): add customers page with form, history and deactivation"
```

---

### Task 14: Catálogo de servicios con duración, precio y sucursales

**Files:**
- Create: `web/src/features/services/ServicesPage.tsx`, `web/src/features/services/ServiceFormDialog.tsx`, `web/src/features/services/ServicesPage.test.tsx`
- Modify: `web/src/app/router.tsx`

**Interfaces:**
- Consumes: `servicesApi`, `queryKeys`, `useAuth`, `ApiError`, `useDebouncedValue`, `formatMoney`, UI components.
- Produces:
  - `ServicesPage` con búsqueda, filtro de estado, tabla, paginación y alta/edición.
  - `ServiceFormDialog({ open, service, onOpenChange, onSaved })`; lista vacía de sucursales significa "todas".
  - Reglas del formulario: duración 5–480, buffers 0–120, precio decimal no negativo, nombre único por empresa (validado por el servidor).

- [ ] **Step 1: Escribir las pruebas de servicios**

`web/src/features/services/ServicesPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import type { Service } from '../../api/services';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { ServicesPage } from './ServicesPage';

const corte: Service = {
  id: 'service-1',
  company: 'company-a',
  name: 'Corte de cabello',
  description: 'Corte clásico',
  duration_minutes: 30,
  price: '12000.00',
  buffer_before_minutes: 0,
  buffer_after_minutes: 10,
  branches: ['branch-1'],
  active: true,
  created_at: '2026-11-01T12:00:00Z',
  updated_at: '2026-11-01T12:00:00Z',
};

const color: Service = {
  ...corte,
  id: 'service-2',
  name: 'Color completo',
  duration_minutes: 90,
  price: '35000.00',
  branches: [],
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <ServicesPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function listHandler(services: () => Service[]) {
  return http.get('http://api.test/api/v1/services/', () => {
    const results = services();
    return HttpResponse.json({
      count: results.length,
      next: null,
      previous: null,
      results,
    });
  });
}

describe('ServicesPage', () => {
  test('lista servicios con duración, precio y sucursales', async () => {
    server.use(listHandler(() => [corte, color]));
    renderPage();

    expect(await screen.findByText('Corte de cabello')).toBeInTheDocument();
    expect(screen.getByText('30 min')).toBeInTheDocument();
    expect(screen.getByText('$ 12.000')).toBeInTheDocument();
    expect(screen.getByText('Providencia')).toBeInTheDocument();
    expect(screen.getByText('Todas las sucursales')).toBeInTheDocument();
  });

  test('crea un servicio con sucursal y valores numéricos', async () => {
    let services = [corte];
    let body: unknown;
    server.use(
      listHandler(() => services),
      http.post('http://api.test/api/v1/services/', async ({ request }) => {
        body = await request.json();
        const created: Service = {
          ...corte,
          id: 'service-3',
          name: 'Corte premium',
          description: '',
          duration_minutes: 45,
          price: '15000',
          buffer_after_minutes: 0,
        };
        services = [...services, created];
        return HttpResponse.json(created, { status: 201 });
      }),
    );
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo servicio' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Corte premium');
    await userEvent.clear(screen.getByLabelText('Duración (minutos)'));
    await userEvent.type(screen.getByLabelText('Duración (minutos)'), '45');
    await userEvent.clear(screen.getByLabelText('Precio'));
    await userEvent.type(screen.getByLabelText('Precio'), '15000');
    await userEvent.click(screen.getByRole('checkbox', { name: 'Providencia' }));
    await userEvent.click(screen.getByRole('button', { name: 'Guardar servicio' }));

    await waitFor(() =>
      expect(body).toEqual({
        name: 'Corte premium',
        description: '',
        duration_minutes: 45,
        price: '15000',
        buffer_before_minutes: 0,
        buffer_after_minutes: 0,
        branches: ['branch-1'],
        active: true,
      }),
    );
    expect(await screen.findByText('Corte premium')).toBeInTheDocument();
  });

  test('muestra el nombre duplicado que rechaza el servidor', async () => {
    server.use(
      listHandler(() => [corte]),
      http.post('http://api.test/api/v1/services/', () =>
        HttpResponse.json(
          { name: ['Ya existe un servicio con este nombre.'] },
          { status: 400 },
        ),
      ),
    );
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo servicio' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Corte de cabello');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar servicio' }));

    const dialog = await screen.findByRole('dialog');
    expect(
      await within(dialog).findAllByText('Ya existe un servicio con este nombre.'),
    ).not.toHaveLength(0);
  });

  test('edita un servicio existente', async () => {
    let services = [corte];
    let body: unknown;
    server.use(
      listHandler(() => services),
      http.patch('http://api.test/api/v1/services/service-1/', async ({ request }) => {
        body = await request.json();
        const updated = { ...corte, active: false };
        services = [updated];
        return HttpResponse.json(updated);
      }),
    );
    renderPage();

    const row = await screen.findByRole('row', { name: /Corte de cabello/ });
    await userEvent.click(within(row).getByRole('button', { name: 'Editar' }));
    expect(screen.getByLabelText('Nombre')).toHaveValue('Corte de cabello');
    await userEvent.click(screen.getByRole('checkbox', { name: 'Servicio activo' }));
    await userEvent.click(screen.getByRole('button', { name: 'Guardar servicio' }));

    await waitFor(() => expect(body).toMatchObject({ name: 'Corte de cabello', active: false }));
    expect(await screen.findByText('Inactivo')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas para verificar que fallan**

Run: `cd web && npm run test -- src/features/services/ServicesPage.test.tsx`

Expected: FAIL porque `ServicesPage` no existe.

- [ ] **Step 3: Implementar el formulario de servicio**

`web/src/features/services/ServiceFormDialog.tsx`:

```tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import type { Service, ServiceInput } from '../../api/services';
import { servicesApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Textarea } from '../../components/ui/Field';

const serviceSchema = z.object({
  name: z.string().trim().min(2, 'Ingresa al menos 2 caracteres.').max(160, 'Máximo 160 caracteres.'),
  description: z.string().max(2000, 'Máximo 2000 caracteres.'),
  duration_minutes: z.coerce
    .number()
    .int('Usa minutos enteros.')
    .min(5, 'La duración mínima es 5 minutos.')
    .max(480, 'La duración máxima es 480 minutos.'),
  price: z
    .string()
    .trim()
    .regex(/^\d+(\.\d{1,2})?$/, 'Usa un monto como 12000 o 12000.50.'),
  buffer_before_minutes: z.coerce
    .number()
    .int('Usa minutos enteros.')
    .min(0, 'El buffer no puede ser negativo.')
    .max(120, 'El buffer máximo es 120 minutos.'),
  buffer_after_minutes: z.coerce
    .number()
    .int('Usa minutos enteros.')
    .min(0, 'El buffer no puede ser negativo.')
    .max(120, 'El buffer máximo es 120 minutos.'),
  branches: z.array(z.string()),
  active: z.boolean(),
});

type ServiceFormValues = z.infer<typeof serviceSchema>;

const FIELD_NAMES = [
  'name',
  'description',
  'duration_minutes',
  'price',
  'buffer_before_minutes',
  'buffer_after_minutes',
  'branches',
] as const;

function valuesFrom(service: Service | null): ServiceFormValues {
  return {
    name: service?.name ?? '',
    description: service?.description ?? '',
    duration_minutes: service?.duration_minutes ?? 30,
    price: service?.price ?? '0',
    buffer_before_minutes: service?.buffer_before_minutes ?? 0,
    buffer_after_minutes: service?.buffer_after_minutes ?? 0,
    branches: service?.branches ?? [],
    active: service?.active ?? true,
  };
}

export function ServiceFormDialog({
  open,
  service,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  service: Service | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const { bootstrap } = useAuth();
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);
  const {
    register,
    handleSubmit,
    setError,
    setValue,
    watch,
    formState: { errors },
  } = useForm<ServiceFormValues>({
    resolver: zodResolver(serviceSchema),
    defaultValues: valuesFrom(service),
  });
  const selectedBranches = watch('branches');

  const mutation = useMutation({
    mutationFn: (values: ServiceInput) =>
      service ? servicesApi.update(service.id, values) : servicesApi.create(values),
    onSuccess: () => {
      onSaved();
      onOpenChange(false);
    },
    onError: (error) => {
      if (!(error instanceof ApiError) || !error.fields) return;
      Object.entries(error.fields).forEach(([field, messages]) => {
        if ((FIELD_NAMES as readonly string[]).includes(field)) {
          setError(field as (typeof FIELD_NAMES)[number], { message: messages[0] });
        }
      });
    },
  });

  function toggleBranch(branchId: string, checked: boolean) {
    const next = checked
      ? [...selectedBranches, branchId]
      : selectedBranches.filter((id) => id !== branchId);
    setValue('branches', next, { shouldValidate: true });
  }

  const onSubmit = handleSubmit((values) => {
    mutation.mutate(values);
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onOpenChange(false);
      }}
      title={service ? 'Editar servicio' : 'Nuevo servicio'}
      description="La duración y los buffers determinan los cupos que ofrece la agenda."
      wide
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {mutation.error ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudo guardar el servicio.'
            }
          />
        ) : null}

        <Field label="Nombre" htmlFor="service-name" error={errors.name?.message}>
          <Input id="service-name" {...register('name')} />
        </Field>

        <Field label="Descripción" htmlFor="service-description" error={errors.description?.message}>
          <Textarea id="service-description" rows={2} {...register('description')} />
        </Field>

        <FormRow>
          <Field
            label="Duración (minutos)"
            htmlFor="service-duration"
            error={errors.duration_minutes?.message}
            hint="Entre 5 y 480 minutos."
          >
            <Input
              id="service-duration"
              type="number"
              min={5}
              max={480}
              step={5}
              {...register('duration_minutes')}
            />
          </Field>
          <Field label="Precio" htmlFor="service-price" error={errors.price?.message}>
            <Input id="service-price" inputMode="decimal" {...register('price')} />
          </Field>
        </FormRow>

        <FormRow>
          <Field
            label="Buffer antes (minutos)"
            htmlFor="service-buffer-before"
            error={errors.buffer_before_minutes?.message}
          >
            <Input
              id="service-buffer-before"
              type="number"
              min={0}
              max={120}
              {...register('buffer_before_minutes')}
            />
          </Field>
          <Field
            label="Buffer después (minutos)"
            htmlFor="service-buffer-after"
            error={errors.buffer_after_minutes?.message}
          >
            <Input
              id="service-buffer-after"
              type="number"
              min={0}
              max={120}
              {...register('buffer_after_minutes')}
            />
          </Field>
        </FormRow>

        <fieldset>
          <legend className="mb-1 block text-sm font-medium text-ink">Sucursales</legend>
          <p className="mb-2 text-xs text-muted">
            Sin selección, el servicio está disponible en todas las sucursales.
          </p>
          <div className="flex flex-wrap gap-3">
            {branches.map((branch) => (
              <label key={branch.id} className="flex items-center gap-2 text-sm text-ink">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-brand"
                  checked={selectedBranches.includes(branch.id)}
                  onChange={(event) => toggleBranch(branch.id, event.target.checked)}
                />
                {branch.name}
              </label>
            ))}
          </div>
          {errors.branches?.message ? (
            <p role="alert" className="mt-1 text-xs text-danger">
              {errors.branches.message}
            </p>
          ) : null}
        </fieldset>

        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" className="h-4 w-4 accent-brand" {...register('active')} />
          Servicio activo
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending} loadingLabel="Guardando…">
            Guardar servicio
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
```

- [ ] **Step 4: Implementar la página de servicios**

`web/src/features/services/ServicesPage.tsx`:

```tsx
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import type { Service, ServiceListParams } from '../../api/services';
import { servicesApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select } from '../../components/ui/Field';
import { PageHeader } from '../../components/ui/PageHeader';
import { Pagination } from '../../components/ui/Pagination';
import { Skeleton } from '../../components/ui/Skeleton';
import { formatMoney } from '../../lib/format';
import { useDebouncedValue } from '../../lib/useDebouncedValue';
import { ServiceFormDialog } from './ServiceFormDialog';

export function ServicesPage() {
  const { company, bootstrap, can } = useAuth();
  const queryClient = useQueryClient();
  const canWrite = can('catalog.write');

  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);
  const [activeFilter, setActiveFilter] = useState<'' | 'true' | 'false'>('');
  const [branchFilter, setBranchFilter] = useState('');
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Service | null>(null);

  const params: ServiceListParams = {
    search: debouncedSearch || undefined,
    active: activeFilter === '' ? undefined : activeFilter === 'true',
    branch: branchFilter || undefined,
    page,
    ordering: 'name',
  };

  const query = useQuery({
    queryKey: queryKeys.services(company?.id ?? '', params),
    queryFn: () => servicesApi.list(params),
    enabled: Boolean(company),
  });

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(service: Service) {
    setEditing(service);
    setFormOpen(true);
  }

  function branchLabel(service: Service) {
    if (service.branches.length === 0) return 'Todas las sucursales';
    return service.branches
      .map((id) => bootstrap?.branches.find((branch) => branch.id === id)?.name ?? 'Sucursal')
      .join(', ');
  }

  const services = query.data?.results ?? [];

  return (
    <section>
      <PageHeader
        title="Servicios"
        description="Catálogo de servicios, duración, precio y sucursales disponibles."
        actions={canWrite ? <Button onClick={openCreate}>Nuevo servicio</Button> : null}
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_10rem_10rem]">
        <Field label="Buscar" htmlFor="service-search">
          <Input
            id="service-search"
            type="search"
            placeholder="Nombre del servicio"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </Field>
        <Field label="Sucursal" htmlFor="service-branch">
          <Select
            id="service-branch"
            value={branchFilter}
            onChange={(event) => {
              setBranchFilter(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Todas</option>
            {(bootstrap?.branches ?? [])
              .filter((branch) => branch.active)
              .map((branch) => (
                <option key={branch.id} value={branch.id}>
                  {branch.name}
                </option>
              ))}
          </Select>
        </Field>
        <Field label="Estado" htmlFor="service-active">
          <Select
            id="service-active"
            value={activeFilter}
            onChange={(event) => {
              setActiveFilter(event.target.value as '' | 'true' | 'false');
              setPage(1);
            }}
          >
            <option value="">Todos</option>
            <option value="true">Activos</option>
            <option value="false">Inactivos</option>
          </Select>
        </Field>
      </div>

      {query.isError ? (
        <ErrorBanner
          message="No se pudieron cargar los servicios."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {query.isPending ? <Skeleton rows={5} /> : null}

      {query.isSuccess && services.length === 0 ? (
        <EmptyState
          title="Sin servicios"
          description={
            debouncedSearch || activeFilter || branchFilter
              ? 'No hay servicios que coincidan con los filtros.'
              : 'Crea el primer servicio para que la agenda ofrezca cupos.'
          }
          action={canWrite ? <Button onClick={openCreate}>Nuevo servicio</Button> : undefined}
        />
      ) : null}

      {services.length > 0 ? (
        <>
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3">Servicio</th>
                  <th scope="col" className="px-4 py-3">Duración</th>
                  <th scope="col" className="px-4 py-3">Precio</th>
                  <th scope="col" className="px-4 py-3">Sucursales</th>
                  <th scope="col" className="px-4 py-3">Estado</th>
                  <th scope="col" className="px-4 py-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {services.map((service) => (
                  <tr key={service.id}>
                    <td className="px-4 py-3">
                      <span className="block font-medium text-ink">{service.name}</span>
                      {service.description ? (
                        <span className="block text-xs text-muted">{service.description}</span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-muted">{service.duration_minutes} min</td>
                    <td className="px-4 py-3 text-muted">{formatMoney(service.price)}</td>
                    <td className="px-4 py-3 text-muted">{branchLabel(service)}</td>
                    <td className="px-4 py-3">
                      <Badge tone={service.active ? 'active' : 'inactive'}>
                        {service.active ? 'Activo' : 'Inactivo'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {canWrite ? (
                        <Button variant="ghost" onClick={() => openEdit(service)}>
                          Editar
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} count={query.data?.count ?? 0} onPage={setPage} />
        </>
      ) : null}

      {formOpen ? (
        <ServiceFormDialog
          open
          service={editing}
          onOpenChange={(next) => {
            if (!next) setFormOpen(false);
          }}
          onSaved={() => {
            void queryClient.invalidateQueries({ queryKey: ['services', company?.id ?? ''] });
          }}
        />
      ) : null}
    </section>
  );
}
```

El filtro de sucursal usa `?branch=` del backend: muestra solo servicios asignados explícitamente a esa sucursal. Un servicio sin sucursales (disponible en todas) aparece únicamente con «Todas».

- [ ] **Step 5: Reemplazar la ruta de servicios**

En `web/src/app/router.tsx`, importar `ServicesPage` y reemplazar el placeholder:

```tsx
import { ServicesPage } from '../features/services/ServicesPage';
```

```tsx
      {
        path: 'servicios',
        element: (
          <RequirePermission permission="catalog.read">
            <ServicesPage />
          </RequirePermission>
        ),
      },
```

- [ ] **Step 6: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test -- src/features/services
npm run build
npm run lint
```

Expected: 4 tests PASS; build y lint sin errores.

- [ ] **Step 7: Validación visual**

- Crear un servicio sin sucursales y comprobar "Todas las sucursales".
- Crear uno con una sucursal y ver el nombre en la tabla.
- Editar duración y precio; el listado se refresca.
- Probar duración 4 y 481, buffer 121 y precio vacío: los mensajes aparecen bajo el campo.
- Repetir en claro y oscuro y a 768 px.

- [ ] **Step 8: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/features/services web/src/app/router.tsx
git commit -m "feat(web): add services catalog with form validation"
```

---

### Task 15: Equipo — trabajadores con color, sucursales y cargo

**Files:**
- Create: `web/src/features/team/WorkersSection.tsx`, `web/src/features/team/WorkerFormDialog.tsx`, `web/src/features/team/WorkersSection.test.tsx`

**Interfaces:**
- Consumes: `teamApi`, `queryKeys`, `useAuth`, `ApiError`, `useDebouncedValue`, UI components.
- Produces:
  - `WorkersSection({ onManageSchedule })`: tabla de trabajadores con búsqueda, filtro de estado, paginación y acción "Horario" que delega en `onManageSchedule(worker)`.
  - `WorkerFormDialog({ open, worker, onOpenChange, onSaved })`.
  - Reglas: al menos una sucursal por trabajador (sin sucursal ningún cupo lo incluye), color hexadecimal de 6 dígitos.

- [ ] **Step 1: Escribir las pruebas de trabajadores**

`web/src/features/team/WorkersSection.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test, vi } from 'vitest';

import type { Worker } from '../../api/team';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { WorkersSection } from './WorkersSection';

const paula: Worker = {
  id: 'worker-1',
  company: 'company-a',
  membership: null,
  first_name: 'Paula',
  last_name: 'Rojas',
  display_name: 'Paula Rojas',
  email: 'paula@example.com',
  phone: '+56922222222',
  job_title: 'Estilista',
  color: '#10B981',
  branches: ['branch-1'],
  active: true,
  created_at: '2026-11-01T12:00:00Z',
  updated_at: '2026-11-01T12:00:00Z',
};

function renderSection() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <WorkersSection onManageSchedule={vi.fn()} />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function listHandler(workers: () => Worker[]) {
  return http.get('http://api.test/api/v1/workers/', () => {
    const results = workers();
    return HttpResponse.json({
      count: results.length,
      next: null,
      previous: null,
      results,
    });
  });
}

describe('WorkersSection', () => {
  test('lista trabajadores con cargo, sucursal y estado', async () => {
    server.use(listHandler(() => [paula]));
    renderSection();

    expect(await screen.findByText('Paula Rojas')).toBeInTheDocument();
    expect(screen.getByText('Estilista')).toBeInTheDocument();
    expect(screen.getByText('Providencia')).toBeInTheDocument();
    expect(screen.getByText('Activo')).toBeInTheDocument();
  });

  test('crea un trabajador con sucursal y color', async () => {
    let workers = [paula];
    let body: unknown;
    server.use(
      listHandler(() => workers),
      http.post('http://api.test/api/v1/workers/', async ({ request }) => {
        body = await request.json();
        const created: Worker = {
          ...paula,
          id: 'worker-2',
          first_name: 'Camila',
          last_name: 'Fuentes',
          display_name: 'Camila Fuentes',
          email: '',
          phone: '',
          job_title: 'Colorista',
        };
        workers = [...workers, created];
        return HttpResponse.json(created, { status: 201 });
      }),
    );
    renderSection();

    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo trabajador' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Camila');
    await userEvent.type(screen.getByLabelText('Apellido'), 'Fuentes');
    await userEvent.type(screen.getByLabelText('Cargo'), 'Colorista');
    await userEvent.click(screen.getByRole('checkbox', { name: 'Providencia' }));
    await userEvent.click(screen.getByRole('button', { name: 'Guardar trabajador' }));

    await waitFor(() =>
      expect(body).toEqual({
        first_name: 'Camila',
        last_name: 'Fuentes',
        email: '',
        phone: '',
        job_title: 'Colorista',
        color: '#10B981',
        branches: ['branch-1'],
        active: true,
        membership: null,
      }),
    );
    expect(await screen.findByText('Camila Fuentes')).toBeInTheDocument();
  });

  test('exige al menos una sucursal antes de enviar', async () => {
    let posted = false;
    server.use(
      listHandler(() => [paula]),
      http.post('http://api.test/api/v1/workers/', () => {
        posted = true;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    renderSection();

    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo trabajador' }));
    await userEvent.type(screen.getByLabelText('Nombre'), 'Camila');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar trabajador' }));

    expect(await screen.findByText('Selecciona al menos una sucursal.')).toBeInTheDocument();
    expect(posted).toBe(false);
  });

  test('edita el cargo de un trabajador', async () => {
    let workers = [paula];
    let body: unknown;
    server.use(
      listHandler(() => workers),
      http.patch('http://api.test/api/v1/workers/worker-1/', async ({ request }) => {
        body = await request.json();
        const updated = { ...paula, job_title: 'Estilista senior' };
        workers = [updated];
        return HttpResponse.json(updated);
      }),
    );
    renderSection();

    const row = await screen.findByRole('row', { name: /Paula Rojas/ });
    await userEvent.click(within(row).getByRole('button', { name: 'Editar' }));
    await userEvent.clear(screen.getByLabelText('Cargo'));
    await userEvent.type(screen.getByLabelText('Cargo'), 'Estilista senior');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar trabajador' }));

    await waitFor(() => expect(body).toMatchObject({ job_title: 'Estilista senior' }));
    expect(await screen.findByText('Estilista senior')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas para verificar que fallan**

Run: `cd web && npm run test -- src/features/team/WorkersSection.test.tsx`

Expected: FAIL porque `WorkersSection` no existe.

- [ ] **Step 3: Implementar el formulario de trabajador**

`web/src/features/team/WorkerFormDialog.tsx`:

```tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import type { Worker, WorkerInput } from '../../api/team';
import { teamApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input } from '../../components/ui/Field';

const workerSchema = z.object({
  first_name: z.string().trim().min(2, 'Ingresa al menos 2 caracteres.').max(120, 'Máximo 120 caracteres.'),
  last_name: z.string().trim().max(120, 'Máximo 120 caracteres.'),
  email: z
    .string()
    .trim()
    .refine(
      (value) => value === '' || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
      'Ingresa un correo válido.',
    ),
  phone: z.string().trim().max(32, 'Máximo 32 caracteres.'),
  job_title: z.string().trim().max(120, 'Máximo 120 caracteres.'),
  color: z.string().regex(/^#[0-9a-fA-F]{6}$/, 'Usa un color hexadecimal como #10B981.'),
  branches: z.array(z.string()).min(1, 'Selecciona al menos una sucursal.'),
  active: z.boolean(),
});

type WorkerFormValues = z.infer<typeof workerSchema>;

const FIELD_NAMES = [
  'first_name',
  'last_name',
  'email',
  'phone',
  'job_title',
  'color',
  'branches',
] as const;

function valuesFrom(worker: Worker | null): WorkerFormValues {
  return {
    first_name: worker?.first_name ?? '',
    last_name: worker?.last_name ?? '',
    email: worker?.email ?? '',
    phone: worker?.phone ?? '',
    job_title: worker?.job_title ?? '',
    color: worker?.color ?? '#10B981',
    branches: worker?.branches ?? [],
    active: worker?.active ?? true,
  };
}

export function WorkerFormDialog({
  open,
  worker,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  worker: Worker | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const { bootstrap } = useAuth();
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);
  const {
    register,
    handleSubmit,
    setError,
    setValue,
    watch,
    formState: { errors },
  } = useForm<WorkerFormValues>({
    resolver: zodResolver(workerSchema),
    defaultValues: valuesFrom(worker),
  });
  const selectedBranches = watch('branches');
  const color = watch('color');

  const mutation = useMutation({
    mutationFn: (values: WorkerInput) =>
      worker ? teamApi.workers.update(worker.id, values) : teamApi.workers.create(values),
    onSuccess: () => {
      onSaved();
      onOpenChange(false);
    },
    onError: (error) => {
      if (!(error instanceof ApiError) || !error.fields) return;
      Object.entries(error.fields).forEach(([field, messages]) => {
        if ((FIELD_NAMES as readonly string[]).includes(field)) {
          setError(field as (typeof FIELD_NAMES)[number], { message: messages[0] });
        }
      });
    },
  });

  function toggleBranch(branchId: string, checked: boolean) {
    const next = checked
      ? [...selectedBranches, branchId]
      : selectedBranches.filter((id) => id !== branchId);
    setValue('branches', next, { shouldValidate: true });
  }

  const onSubmit = handleSubmit((values) => {
    mutation.mutate({ ...values, membership: worker?.membership ?? null });
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onOpenChange(false);
      }}
      title={worker ? 'Editar trabajador' : 'Nuevo trabajador'}
      description="El trabajador recibe cupos solo en las sucursales seleccionadas."
      wide
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {mutation.error ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudo guardar el trabajador.'
            }
          />
        ) : null}

        <FormRow>
          <Field label="Nombre" htmlFor="worker-first-name" error={errors.first_name?.message}>
            <Input id="worker-first-name" autoComplete="given-name" {...register('first_name')} />
          </Field>
          <Field label="Apellido" htmlFor="worker-last-name" error={errors.last_name?.message}>
            <Input id="worker-last-name" autoComplete="family-name" {...register('last_name')} />
          </Field>
        </FormRow>

        <FormRow>
          <Field label="Correo" htmlFor="worker-email" error={errors.email?.message}>
            <Input id="worker-email" type="email" autoComplete="email" {...register('email')} />
          </Field>
          <Field label="Teléfono" htmlFor="worker-phone" error={errors.phone?.message}>
            <Input id="worker-phone" type="tel" autoComplete="tel" {...register('phone')} />
          </Field>
        </FormRow>

        <FormRow>
          <Field label="Cargo" htmlFor="worker-job-title" error={errors.job_title?.message}>
            <Input id="worker-job-title" {...register('job_title')} />
          </Field>
          <Field label="Color" htmlFor="worker-color" error={errors.color?.message}>
            <div className="flex items-center gap-3">
              <input
                id="worker-color"
                type="color"
                className="h-10 w-16 rounded-md border border-line bg-panel p-1"
                {...register('color')}
              />
              <span className="text-sm text-muted">{color}</span>
            </div>
          </Field>
        </FormRow>

        <fieldset>
          <legend className="mb-1 block text-sm font-medium text-ink">Sucursales</legend>
          <p className="mb-2 text-xs text-muted">
            La agenda solo ofrece cupos del trabajador en estas sucursales.
          </p>
          <div className="flex flex-wrap gap-3">
            {branches.map((branch) => (
              <label key={branch.id} className="flex items-center gap-2 text-sm text-ink">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-brand"
                  checked={selectedBranches.includes(branch.id)}
                  onChange={(event) => toggleBranch(branch.id, event.target.checked)}
                />
                {branch.name}
              </label>
            ))}
          </div>
          {errors.branches?.message ? (
            <p role="alert" className="mt-1 text-xs text-danger">
              {errors.branches.message}
            </p>
          ) : null}
        </fieldset>

        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" className="h-4 w-4 accent-brand" {...register('active')} />
          Trabajador activo
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending} loadingLabel="Guardando…">
            Guardar trabajador
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
```

- [ ] **Step 4: Implementar la sección de trabajadores**

`web/src/features/team/WorkersSection.tsx`:

```tsx
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { teamApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import type { Worker } from '../../api/team';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select } from '../../components/ui/Field';
import { Pagination } from '../../components/ui/Pagination';
import { Skeleton } from '../../components/ui/Skeleton';
import { useDebouncedValue } from '../../lib/useDebouncedValue';
import { WorkerFormDialog } from './WorkerFormDialog';

export function WorkersSection({
  onManageSchedule,
}: {
  onManageSchedule: (worker: Worker) => void;
}) {
  const { company, bootstrap, can } = useAuth();
  const queryClient = useQueryClient();
  const canWrite = can('workforce.write');

  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);
  const [activeFilter, setActiveFilter] = useState<'' | 'true' | 'false'>('');
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Worker | null>(null);

  const params = {
    search: debouncedSearch || undefined,
    active: activeFilter === '' ? undefined : activeFilter === 'true',
    page,
    ordering: 'last_name',
  };

  const query = useQuery({
    queryKey: queryKeys.workers(company?.id ?? '', params),
    queryFn: () => teamApi.workers.list(params),
    enabled: Boolean(company),
  });

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(worker: Worker) {
    setEditing(worker);
    setFormOpen(true);
  }

  function branchLabel(worker: Worker) {
    return worker.branches
      .map((id) => bootstrap?.branches.find((branch) => branch.id === id)?.name ?? 'Sucursal')
      .join(', ');
  }

  const workers = query.data?.results ?? [];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div className="grid flex-1 gap-3 sm:grid-cols-[1fr_12rem]">
          <Field label="Buscar" htmlFor="worker-search">
            <Input
              id="worker-search"
              type="search"
              placeholder="Nombre, correo o cargo"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
            />
          </Field>
          <Field label="Estado" htmlFor="worker-active">
            <Select
              id="worker-active"
              value={activeFilter}
              onChange={(event) => {
                setActiveFilter(event.target.value as '' | 'true' | 'false');
                setPage(1);
              }}
            >
              <option value="">Todos</option>
              <option value="true">Activos</option>
              <option value="false">Inactivos</option>
            </Select>
          </Field>
        </div>
        {canWrite ? <Button onClick={openCreate}>Nuevo trabajador</Button> : null}
      </div>

      {query.isError ? (
        <ErrorBanner
          message="No se pudieron cargar los trabajadores."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {query.isPending ? <Skeleton rows={4} /> : null}

      {query.isSuccess && workers.length === 0 ? (
        <EmptyState
          title="Sin trabajadores"
          description={
            debouncedSearch || activeFilter
              ? 'No hay trabajadores que coincidan con los filtros.'
              : 'Crea el primer trabajador y define su horario para abrir cupos.'
          }
          action={canWrite ? <Button onClick={openCreate}>Nuevo trabajador</Button> : undefined}
        />
      ) : null}

      {workers.length > 0 ? (
        <>
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3">Trabajador</th>
                  <th scope="col" className="px-4 py-3">Contacto</th>
                  <th scope="col" className="px-4 py-3">Sucursales</th>
                  <th scope="col" className="px-4 py-3">Estado</th>
                  <th scope="col" className="px-4 py-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {workers.map((worker) => (
                  <tr key={worker.id}>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-2 font-medium text-ink">
                        <span
                          aria-hidden
                          className="h-2.5 w-2.5 rounded-full"
                          style={{ backgroundColor: worker.color }}
                        />
                        {worker.display_name}
                      </span>
                      {worker.job_title ? (
                        <span className="block text-xs text-muted">{worker.job_title}</span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-muted">
                      <span className="block">{worker.email || 'Sin correo'}</span>
                      <span className="block text-xs">{worker.phone || 'Sin teléfono'}</span>
                    </td>
                    <td className="px-4 py-3 text-muted">{branchLabel(worker) || '—'}</td>
                    <td className="px-4 py-3">
                      <Badge tone={worker.active ? 'active' : 'inactive'}>
                        {worker.active ? 'Activo' : 'Inactivo'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap justify-end gap-1">
                        <Button variant="ghost" onClick={() => onManageSchedule(worker)}>
                          Horario
                        </Button>
                        {canWrite ? (
                          <Button variant="ghost" onClick={() => openEdit(worker)}>
                            Editar
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} count={query.data?.count ?? 0} onPage={setPage} />
        </>
      ) : null}

      {formOpen ? (
        <WorkerFormDialog
          open
          worker={editing}
          onOpenChange={(next) => {
            if (!next) setFormOpen(false);
          }}
          onSaved={() => {
            void queryClient.invalidateQueries({ queryKey: ['workers', company?.id ?? ''] });
          }}
        />
      ) : null}
    </div>
  );
}
```

- [ ] **Step 5: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test -- src/features/team/WorkersSection.test.tsx
npm run build
npm run lint
```

Expected: 4 tests PASS; build y lint sin errores.

- [ ] **Step 6: Validación visual**

- Crear un trabajador con una sucursal y ver el punto de color.
- Intentar guardar sin sucursal; el mensaje aparece y no se envía.
- Editar cargo, teléfono y estado; la tabla se refresca.
- Abrir el selector de color y comprobar que el valor hexadecimal se actualiza.
- Repetir en claro y oscuro y a 768 px.

- [ ] **Step 7: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/features/team
git commit -m "feat(web): add workers section with color and branch assignment"
```

---

### Task 16: Equipo — pestañas y horarios semanales con pausas

**Files:**
- Create: `web/src/features/team/TeamPage.tsx`, `web/src/features/team/ScheduleSection.tsx`, `web/src/features/team/ScheduleSlotDialog.tsx`, `web/src/features/team/ScheduleSection.test.tsx`, `web/src/features/team/TeamPage.test.tsx`
- Modify: `web/src/app/router.tsx`

**Interfaces:**
- Consumes: `teamApi`, `queryKeys`, `useAuth`, `weekdayLabel`, `ApiError`, UI components, `WorkersSection` de la tarea 15.
- Produces:
  - `TeamPage` con pestañas `Trabajadores` y `Horario`; `Horario` desde la tabla selecciona el trabajador.
  - `ScheduleSection({ workerId, onWorkerChange })`: selector de trabajador, turnos y pausas agrupados por sucursal, alta y eliminación.
  - `ScheduleSlotDialog({ kind, workerId, branchIds, onOpenChange, onSaved })` con `kind: 'hours' | 'break'`; solo ofrece las sucursales asignadas al trabajador; día 0–6 (lunes = 0), horas `HH:MM`, término posterior al inicio.

- [ ] **Step 1: Escribir las pruebas de horarios**

`web/src/features/team/ScheduleSection.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test, vi } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { ScheduleSection } from './ScheduleSection';

const worker = {
  id: 'worker-1',
  company: 'company-a',
  membership: null,
  first_name: 'Paula',
  last_name: 'Rojas',
  display_name: 'Paula Rojas',
  email: '',
  phone: '',
  job_title: 'Estilista',
  color: '#10B981',
  branches: ['branch-1'],
  active: true,
  created_at: '2026-11-01T12:00:00Z',
  updated_at: '2026-11-01T12:00:00Z',
};

const hours = {
  id: 'hours-1',
  worker: 'worker-1',
  branch: 'branch-1',
  weekday: 0,
  start_time: '09:00:00',
  end_time: '13:00:00',
};

const pause = {
  ...hours,
  id: 'break-1',
  start_time: '11:00:00',
  end_time: '11:30:00',
  label: 'Almuerzo',
};

function renderSection() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <ScheduleSection workerId="worker-1" onWorkerChange={vi.fn()} />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function baseHandlers() {
  return [
    http.get('http://api.test/api/v1/workers/', () =>
      HttpResponse.json({ count: 1, next: null, previous: null, results: [worker] }),
    ),
    http.get('http://api.test/api/v1/working-hours/', () =>
      HttpResponse.json({ count: 1, next: null, previous: null, results: [hours] }),
    ),
    http.get('http://api.test/api/v1/breaks/', () =>
      HttpResponse.json({ count: 1, next: null, previous: null, results: [pause] }),
    ),
  ];
}

describe('ScheduleSection', () => {
  test('muestra turnos y pausas agrupados por sucursal', async () => {
    server.use(...baseHandlers());
    renderSection();

    expect(await screen.findByText('Providencia')).toBeInTheDocument();
    expect(screen.getByText('Lunes · 09:00 – 13:00')).toBeInTheDocument();
    expect(screen.getByText('Lunes · 11:00 – 11:30')).toBeInTheDocument();
    expect(screen.getByText('Almuerzo')).toBeInTheDocument();
  });

  test('crea un turno para el trabajador', async () => {
    let body: unknown;
    server.use(
      ...baseHandlers(),
      http.post('http://api.test/api/v1/working-hours/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...hours, id: 'hours-2', weekday: 1 }, { status: 201 });
      }),
    );
    renderSection();

    await userEvent.click(await screen.findByRole('button', { name: 'Agregar horario' }));
    await userEvent.selectOptions(screen.getByLabelText('Día'), '1');
    await userEvent.clear(screen.getByLabelText('Inicio'));
    await userEvent.type(screen.getByLabelText('Inicio'), '10:00');
    await userEvent.clear(screen.getByLabelText('Término'));
    await userEvent.type(screen.getByLabelText('Término'), '18:00');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar horario' }));

    await waitFor(() =>
      expect(body).toEqual({
        worker: 'worker-1',
        branch: 'branch-1',
        weekday: 1,
        start_time: '10:00',
        end_time: '18:00',
      }),
    );
  });

  test('rechaza un término anterior al inicio', async () => {
    let posted = false;
    server.use(
      ...baseHandlers(),
      http.post('http://api.test/api/v1/working-hours/', () => {
        posted = true;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    renderSection();

    await userEvent.click(await screen.findByRole('button', { name: 'Agregar horario' }));
    await userEvent.clear(screen.getByLabelText('Término'));
    await userEvent.type(screen.getByLabelText('Término'), '08:00');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar horario' }));

    expect(
      await screen.findByText('La hora de término debe ser posterior al inicio.'),
    ).toBeInTheDocument();
    expect(posted).toBe(false);
  });

  test('elimina un turno tras confirmar', async () => {
    let deleted = '';
    server.use(
      ...baseHandlers(),
      http.delete('http://api.test/api/v1/working-hours/hours-1/', () => {
        deleted = 'hours-1';
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderSection();

    await userEvent.click(
      await screen.findByRole('button', { name: 'Eliminar Lunes 09:00' }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar' }));

    await waitFor(() => expect(deleted).toBe('hours-1'));
  });
});
```

`web/src/features/team/TeamPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { TeamPage } from './TeamPage';

const worker = {
  id: 'worker-1',
  company: 'company-a',
  membership: null,
  first_name: 'Paula',
  last_name: 'Rojas',
  display_name: 'Paula Rojas',
  email: '',
  phone: '',
  job_title: 'Estilista',
  color: '#10B981',
  branches: ['branch-1'],
  active: true,
  created_at: '2026-11-01T12:00:00Z',
  updated_at: '2026-11-01T12:00:00Z',
};

describe('TeamPage', () => {
  test('abre el horario del trabajador desde la tabla', async () => {
    server.use(
      http.get('http://api.test/api/v1/workers/', () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [worker] }),
      ),
      http.get('http://api.test/api/v1/working-hours/', () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      http.get('http://api.test/api/v1/breaks/', () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <AuthContext.Provider value={makeAuthValue()}>
        <QueryClientProvider client={queryClient}>
          <TeamPage />
        </QueryClientProvider>
      </AuthContext.Provider>,
    );

    const row = await screen.findByRole('row', { name: /Paula Rojas/ });
    await userEvent.click(screen.getByRole('button', { name: 'Horario' }));
    expect(row).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Horario' })).toHaveAttribute('aria-selected', 'true');
    expect(await screen.findByText('Sin turnos.')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas para verificar que fallan**

Run: `cd web && npm run test -- src/features/team/ScheduleSection.test.tsx src/features/team/TeamPage.test.tsx`

Expected: FAIL porque las páginas no existen.

- [ ] **Step 3: Implementar el diálogo de turnos y pausas**

`web/src/features/team/ScheduleSlotDialog.tsx`:

```tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import { teamApi } from '../../api/runtime';
import type { Break, Weekday, WorkingHours } from '../../api/team';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Select } from '../../components/ui/Field';
import { WEEKDAYS } from '../../lib/format';

const slotSchema = z
  .object({
    branch: z.string().min(1, 'Selecciona una sucursal.'),
    weekday: z.coerce.number().int().min(0).max(6),
    start_time: z
      .string()
      .regex(/^([01]\d|2[0-3]):[0-5]\d$/, 'Usa el formato HH:MM.'),
    end_time: z
      .string()
      .regex(/^([01]\d|2[0-3]):[0-5]\d$/, 'Usa el formato HH:MM.'),
    label: z.string().trim().max(120, 'Máximo 120 caracteres.'),
  })
  .refine((values) => values.end_time > values.start_time, {
    message: 'La hora de término debe ser posterior al inicio.',
    path: ['end_time'],
  });

type SlotFormValues = z.infer<typeof slotSchema>;

export function ScheduleSlotDialog({
  kind,
  workerId,
  branchIds,
  onOpenChange,
  onSaved,
}: {
  kind: 'hours' | 'break';
  workerId: string;
  branchIds: string[];
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const { bootstrap } = useAuth();
  const branches = (bootstrap?.branches ?? []).filter(
    (branch) => branch.active && branchIds.includes(branch.id),
  );
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SlotFormValues>({
    resolver: zodResolver(slotSchema),
    defaultValues: {
      branch: branches[0]?.id ?? '',
      weekday: 0,
      start_time: kind === 'break' ? '12:00' : '09:00',
      end_time: kind === 'break' ? '13:00' : '18:00',
      label: kind === 'break' ? 'Almuerzo' : '',
    },
  });

  const mutation = useMutation({
    mutationFn: (values: SlotFormValues): Promise<WorkingHours | Break> => {
      const payload = {
        worker: workerId,
        branch: values.branch,
        weekday: values.weekday as Weekday,
        start_time: values.start_time,
        end_time: values.end_time,
      };
      return kind === 'hours'
        ? teamApi.workingHours.create(payload)
        : teamApi.breaks.create({ ...payload, label: values.label });
    },
    onSuccess: () => {
      onSaved();
      onOpenChange(false);
    },
  });

  const onSubmit = handleSubmit((values) => {
    mutation.mutate(values);
  });

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onOpenChange(false);
      }}
      title={kind === 'hours' ? 'Agregar horario' : 'Agregar pausa'}
      description={
        kind === 'hours'
          ? 'El turno se repite cada semana en la sucursal elegida.'
          : 'La pausa se excluye de los cupos disponibles.'
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {mutation.error ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudo guardar el bloque.'
            }
          />
        ) : null}

        <Field label="Sucursal" htmlFor="slot-branch" error={errors.branch?.message}>
          <Select id="slot-branch" {...register('branch')}>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </Select>
        </Field>

        <FormRow>
          <Field label="Día" htmlFor="slot-weekday" error={errors.weekday?.message}>
            <Select id="slot-weekday" {...register('weekday')}>
              {WEEKDAYS.map((label, index) => (
                <option key={label} value={index}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          {kind === 'break' ? (
            <Field label="Etiqueta" htmlFor="slot-label" error={errors.label?.message}>
              <Input id="slot-label" {...register('label')} />
            </Field>
          ) : null}
        </FormRow>

        <FormRow>
          <Field label="Inicio" htmlFor="slot-start" error={errors.start_time?.message}>
            <Input id="slot-start" type="time" {...register('start_time')} />
          </Field>
          <Field label="Término" htmlFor="slot-end" error={errors.end_time?.message}>
            <Input id="slot-end" type="time" {...register('end_time')} />
          </Field>
        </FormRow>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            type="submit"
            loading={mutation.isPending}
            loadingLabel="Guardando…"
          >
            {kind === 'hours' ? 'Guardar horario' : 'Guardar pausa'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
```

- [ ] **Step 4: Implementar la sección de horarios**

`web/src/features/team/ScheduleSection.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError } from '../../api/client';
import { teamApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import type { Break, WorkingHours } from '../../api/team';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/Dialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Select } from '../../components/ui/Field';
import { Skeleton } from '../../components/ui/Skeleton';
import { weekdayLabel } from '../../lib/format';
import { ScheduleSlotDialog } from './ScheduleSlotDialog';

type PendingDelete = { kind: 'hours' | 'break'; id: string; label: string };

function slotLabel(slot: WorkingHours | Break) {
  return `${weekdayLabel(slot.weekday)} · ${slot.start_time.slice(0, 5)} – ${slot.end_time.slice(0, 5)}`;
}

export function ScheduleSection({
  workerId,
  onWorkerChange,
}: {
  workerId: string;
  onWorkerChange: (workerId: string) => void;
}) {
  const { company, bootstrap, can } = useAuth();
  const queryClient = useQueryClient();
  const canWrite = can('workforce.write');

  const [dialogKind, setDialogKind] = useState<'hours' | 'break' | null>(null);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);

  const workersQuery = useQuery({
    queryKey: queryKeys.workers(company?.id ?? '', { active: true, page: 1 }),
    queryFn: () => teamApi.workers.list({ active: true, page: 1 }),
    enabled: Boolean(company),
  });
  const workers = workersQuery.data?.results ?? [];
  const selectedWorkerId = workerId || workers[0]?.id || '';
  const selectedWorker = workers.find((worker) => worker.id === selectedWorkerId);

  const hoursQuery = useQuery({
    queryKey: queryKeys.workingHours(company?.id ?? '', selectedWorkerId),
    queryFn: () => teamApi.workingHours.list({ worker: selectedWorkerId, page: 1 }),
    enabled: Boolean(company && selectedWorkerId),
  });
  const breaksQuery = useQuery({
    queryKey: queryKeys.breaks(company?.id ?? '', selectedWorkerId),
    queryFn: () => teamApi.breaks.list({ worker: selectedWorkerId, page: 1 }),
    enabled: Boolean(company && selectedWorkerId),
  });

  const remove = useMutation({
    mutationFn: (pending: PendingDelete) =>
      pending.kind === 'hours'
        ? teamApi.workingHours.remove(pending.id)
        : teamApi.breaks.remove(pending.id),
    onSuccess: () => {
      setPendingDelete(null);
      void queryClient.invalidateQueries({ queryKey: ['working-hours', company?.id ?? ''] });
      void queryClient.invalidateQueries({ queryKey: ['breaks', company?.id ?? ''] });
    },
  });

  function invalidateSchedule() {
    void queryClient.invalidateQueries({ queryKey: ['working-hours', company?.id ?? ''] });
    void queryClient.invalidateQueries({ queryKey: ['breaks', company?.id ?? ''] });
  }

  const branchIds = selectedWorker?.branches ?? [];
  const branches = (bootstrap?.branches ?? []).filter(
    (branch) => branchIds.length === 0 || branchIds.includes(branch.id),
  );
  const hours = hoursQuery.data?.results ?? [];
  const breaks = breaksQuery.data?.results ?? [];
  const loading = workersQuery.isPending || hoursQuery.isPending || breaksQuery.isPending;
  const failed = workersQuery.isError || hoursQuery.isError || breaksQuery.isError;
  const removeError =
    remove.error instanceof ApiError
      ? remove.error.message
      : remove.error
        ? 'No se pudo eliminar el bloque.'
        : null;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <Field label="Trabajador" htmlFor="schedule-worker" className="w-full sm:w-72">
          <Select
            id="schedule-worker"
            value={selectedWorkerId}
            onChange={(event) => onWorkerChange(event.target.value)}
          >
            {workers.map((worker) => (
              <option key={worker.id} value={worker.id}>
                {worker.display_name}
              </option>
            ))}
          </Select>
        </Field>
        {canWrite && selectedWorkerId && branches.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setDialogKind('break')}>
              Agregar pausa
            </Button>
            <Button onClick={() => setDialogKind('hours')}>Agregar horario</Button>
          </div>
        ) : null}
      </div>

      {removeError ? <ErrorBanner message={removeError} /> : null}
      {failed ? (
        <ErrorBanner
          message="No se pudo cargar el horario."
          onRetry={() => {
            void workersQuery.refetch();
            void hoursQuery.refetch();
            void breaksQuery.refetch();
          }}
        />
      ) : null}
      {loading ? <Skeleton rows={3} /> : null}

      {!loading && workers.length === 0 ? (
        <EmptyState
          title="Sin trabajadores"
          description="Crea un trabajador en la pestaña Trabajadores antes de definir horarios."
        />
      ) : null}

      {!loading && selectedWorker && branches.length === 0 ? (
        <EmptyState
          title="Sin sucursales asignadas"
          description="Asigna al menos una sucursal al trabajador para definir su horario."
        />
      ) : null}

      <div className="space-y-4">
        {branches.map((branch) => {
          const branchHours = hours
            .filter((slot) => slot.branch === branch.id)
            .sort((a, b) => a.weekday - b.weekday || a.start_time.localeCompare(b.start_time));
          const branchBreaks = breaks
            .filter((slot) => slot.branch === branch.id)
            .sort((a, b) => a.weekday - b.weekday || a.start_time.localeCompare(b.start_time));

          return (
            <div key={branch.id} className="rounded-lg border border-line bg-panel p-4">
              <h2 className="text-base font-semibold text-ink">{branch.name}</h2>
              <div className="mt-3 grid gap-4 md:grid-cols-2">
                <div>
                  <h3 className="mb-2 text-sm font-medium text-ink">Turnos</h3>
                  {branchHours.length === 0 ? (
                    <p className="text-sm text-muted">Sin turnos.</p>
                  ) : (
                    <ul className="divide-y divide-line">
                      {branchHours.map((slot) => (
                        <li
                          key={slot.id}
                          className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"
                        >
                          <span className="text-ink">{slotLabel(slot)}</span>
                          {canWrite ? (
                            <Button
                              variant="ghost"
                              aria-label={`Eliminar ${weekdayLabel(slot.weekday)} ${slot.start_time.slice(0, 5)}`}
                              onClick={() =>
                                setPendingDelete({
                                  kind: 'hours',
                                  id: slot.id,
                                  label: slotLabel(slot),
                                })
                              }
                            >
                              Eliminar
                            </Button>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div>
                  <h3 className="mb-2 text-sm font-medium text-ink">Pausas</h3>
                  {branchBreaks.length === 0 ? (
                    <p className="text-sm text-muted">Sin pausas.</p>
                  ) : (
                    <ul className="divide-y divide-line">
                      {branchBreaks.map((slot) => (
                        <li
                          key={slot.id}
                          className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"
                        >
                          <span className="text-ink">
                            {slotLabel(slot)}
                            {slot.label ? (
                              <span className="ml-2 text-xs text-muted">{slot.label}</span>
                            ) : null}
                          </span>
                          {canWrite ? (
                            <Button
                              variant="ghost"
                              aria-label={`Eliminar pausa ${weekdayLabel(slot.weekday)} ${slot.start_time.slice(0, 5)}`}
                              onClick={() =>
                                setPendingDelete({
                                  kind: 'break',
                                  id: slot.id,
                                  label: slotLabel(slot),
                                })
                              }
                            >
                              Eliminar
                            </Button>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {dialogKind ? (
        <ScheduleSlotDialog
          kind={dialogKind}
          workerId={selectedWorkerId}
          branchIds={branchIds}
          onOpenChange={(next) => {
            if (!next) setDialogKind(null);
          }}
          onSaved={invalidateSchedule}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        onOpenChange={(next) => {
          if (!next) setPendingDelete(null);
        }}
        title={pendingDelete?.kind === 'break' ? 'Eliminar pausa' : 'Eliminar turno'}
        description={
          pendingDelete
            ? `Se quitará ${pendingDelete.label} del horario semanal. Las reservas existentes no se modifican.`
            : ''
        }
        confirmLabel="Eliminar"
        loading={remove.isPending}
        onConfirm={() => {
          if (pendingDelete) remove.mutate(pendingDelete);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 5: Implementar la página de equipo**

`web/src/features/team/TeamPage.tsx`:

```tsx
import { useState } from 'react';

import { PageHeader } from '../../components/ui/PageHeader';
import { ScheduleSection } from './ScheduleSection';
import { WorkersSection } from './WorkersSection';

type TeamTab = 'workers' | 'schedule';

const TABS: { id: TeamTab; label: string }[] = [
  { id: 'workers', label: 'Trabajadores' },
  { id: 'schedule', label: 'Horario' },
];

export function TeamPage() {
  const [tab, setTab] = useState<TeamTab>('workers');
  const [workerId, setWorkerId] = useState('');

  return (
    <section>
      <PageHeader
        title="Equipo"
        description="Trabajadores, sucursales, turnos semanales y pausas."
      />

      <div role="tablist" aria-label="Secciones de equipo" className="mb-4 flex gap-1 border-b border-line">
        {TABS.map((item) => (
          <button
            key={item.id}
            role="tab"
            type="button"
            id={`team-tab-${item.id}`}
            aria-selected={tab === item.id}
            aria-controls={`team-panel-${item.id}`}
            onClick={() => setTab(item.id)}
            className={`px-4 py-2 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
              tab === item.id
                ? 'border-b-2 border-brand text-ink'
                : 'text-muted hover:text-ink'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id="team-panel-workers" aria-labelledby="team-tab-workers" hidden={tab !== 'workers'}>
        <WorkersSection
          onManageSchedule={(worker) => {
            setWorkerId(worker.id);
            setTab('schedule');
          }}
        />
      </div>
      <div role="tabpanel" id="team-panel-schedule" aria-labelledby="team-tab-schedule" hidden={tab !== 'schedule'}>
        {tab === 'schedule' ? (
          <ScheduleSection workerId={workerId} onWorkerChange={setWorkerId} />
        ) : null}
      </div>
    </section>
  );
}
```

- [ ] **Step 6: Reemplazar la ruta de equipo**

En `web/src/app/router.tsx`, importar `TeamPage` y reemplazar el placeholder:

```tsx
import { TeamPage } from '../features/team/TeamPage';
```

```tsx
      {
        path: 'equipo',
        element: (
          <RequirePermission permission="workforce.read">
            <TeamPage />
          </RequirePermission>
        ),
      },
```

- [ ] **Step 7: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test -- src/features/team
npm run build
npm run lint
```

Expected: 9 tests PASS (4 trabajadores, 4 horarios, 1 integración); build y lint sin errores.

- [ ] **Step 8: Validación visual**

- Entrar por "Horario" desde un trabajador y comprobar que queda seleccionado.
- Agregar un turno de lunes, un turno con solapamiento y una pausa; el solapamiento muestra el error del servidor.
- Eliminar un turno y una pausa; desaparecen de la lista.
- Cambiar de trabajador y verificar que los turnos cambian.
- Repetir en claro y oscuro, con teclado y a 768 px.

- [ ] **Step 9: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/features/team web/src/app/router.tsx
git commit -m "feat(web): add team page with weekly schedule and breaks"
```

---

### Task 17: Equipo — ausencias y bloqueos puntuales

**Files:**
- Create: `web/src/features/team/ExceptionsSection.tsx`, `web/src/features/team/ExceptionDialog.tsx`, `web/src/features/team/ExceptionsSection.test.tsx`
- Modify: `web/src/features/team/TeamPage.tsx`

**Interfaces:**
- Consumes: `teamApi.timeOff`, `teamApi.blockedSlots`, `queryKeys.timeOff`, `queryKeys.blockedSlots`, `dateTimeLocalToISO`, `formatDateTime`, `formatTime`, `todayInZone`, `ApiError`, UI components.
- Produces:
  - `TimeOffSection({ workerId, onWorkerChange })` y `BlockedSlotsSection({ workerId, onWorkerChange })`, ambas sobre `ExceptionsSection`.
  - `ExceptionsSection({ kind, workerId, onWorkerChange })` con `kind: 'timeOff' | 'blocked'`.
  - `ExceptionDialog({ kind, workerId, onOpenChange, onSaved })`: fechas locales convertidas a UTC con la zona de la sucursal; sucursal vacía significa todas.
  - `TeamPage` agrega las pestañas `Ausencias` y `Bloqueos`.

- [ ] **Step 1: Escribir las pruebas de ausencias y bloqueos**

`web/src/features/team/ExceptionsSection.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test, vi } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { ExceptionsSection } from './ExceptionsSection';

const worker = {
  id: 'worker-1',
  company: 'company-a',
  membership: null,
  first_name: 'Paula',
  last_name: 'Rojas',
  display_name: 'Paula Rojas',
  email: '',
  phone: '',
  job_title: 'Estilista',
  color: '#10B981',
  branches: ['branch-1'],
  active: true,
  created_at: '2026-11-01T12:00:00Z',
  updated_at: '2026-11-01T12:00:00Z',
};

const vacation = {
  id: 'timeoff-1',
  worker: 'worker-1',
  branch: 'branch-1',
  starts_at: '2026-11-20T13:00:00Z',
  ends_at: '2026-11-20T15:00:00Z',
  reason: 'Vacaciones',
};

const errand = {
  id: 'blocked-1',
  worker: 'worker-1',
  branch: null,
  starts_at: '2026-11-21T13:00:00Z',
  ends_at: '2026-11-21T14:00:00Z',
  reason: 'Trámite',
};

function renderSection(kind: 'timeOff' | 'blocked') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <ExceptionsSection kind={kind} workerId="worker-1" onWorkerChange={vi.fn()} />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function workersHandler() {
  return http.get('http://api.test/api/v1/workers/', () =>
    HttpResponse.json({ count: 1, next: null, previous: null, results: [worker] }),
  );
}

describe('ExceptionsSection', () => {
  test('lista ausencias con motivo y sucursal', async () => {
    server.use(
      workersHandler(),
      http.get('http://api.test/api/v1/time-off/', () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [vacation] }),
      ),
    );
    renderSection('timeOff');

    expect(await screen.findByText(/Vacaciones/)).toBeInTheDocument();
    expect(screen.getByText(/Providencia/)).toBeInTheDocument();
    expect(screen.getByText(/10:00/)).toBeInTheDocument();
  });

  test('crea una ausencia y convierte la hora local a UTC', async () => {
    let body: unknown;
    server.use(
      workersHandler(),
      http.get('http://api.test/api/v1/time-off/', () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      http.post('http://api.test/api/v1/time-off/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(vacation, { status: 201 });
      }),
    );
    renderSection('timeOff');

    await userEvent.click(await screen.findByRole('button', { name: 'Nueva ausencia' }));
    fireEvent.change(screen.getByLabelText('Inicio'), {
      target: { value: '2026-11-20T10:00' },
    });
    fireEvent.change(screen.getByLabelText('Término'), {
      target: { value: '2026-11-20T12:00' },
    });
    await userEvent.type(screen.getByLabelText('Motivo'), 'Vacaciones');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar ausencia' }));

    await waitFor(() =>
      expect(body).toEqual({
        worker: 'worker-1',
        branch: 'branch-1',
        starts_at: '2026-11-20T13:00:00.000Z',
        ends_at: '2026-11-20T15:00:00.000Z',
        reason: 'Vacaciones',
      }),
    );
  });

  test('rechaza una ausencia que termina antes de empezar', async () => {
    let posted = false;
    server.use(
      workersHandler(),
      http.get('http://api.test/api/v1/time-off/', () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      http.post('http://api.test/api/v1/time-off/', () => {
        posted = true;
        return HttpResponse.json(vacation, { status: 201 });
      }),
    );
    renderSection('timeOff');

    await userEvent.click(await screen.findByRole('button', { name: 'Nueva ausencia' }));
    fireEvent.change(screen.getByLabelText('Inicio'), {
      target: { value: '2026-11-20T12:00' },
    });
    fireEvent.change(screen.getByLabelText('Término'), {
      target: { value: '2026-11-20T10:00' },
    });
    await userEvent.click(screen.getByRole('button', { name: 'Guardar ausencia' }));

    expect(
      await screen.findByText('El término debe ser posterior al inicio.'),
    ).toBeInTheDocument();
    expect(posted).toBe(false);
  });

  test('lista y crea un bloqueo sin sucursal', async () => {
    let body: unknown;
    server.use(
      workersHandler(),
      http.get('http://api.test/api/v1/blocked-slots/', () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [errand] }),
      ),
      http.post('http://api.test/api/v1/blocked-slots/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(errand, { status: 201 });
      }),
    );
    renderSection('blocked');

    expect(await screen.findByText(/Trámite/)).toBeInTheDocument();
    expect(screen.getByText(/Todas las sucursales/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Nuevo bloqueo' }));
    await userEvent.selectOptions(screen.getByLabelText('Sucursal'), '');
    fireEvent.change(screen.getByLabelText('Inicio'), {
      target: { value: '2026-11-21T10:00' },
    });
    fireEvent.change(screen.getByLabelText('Término'), {
      target: { value: '2026-11-21T11:00' },
    });
    await userEvent.type(screen.getByLabelText('Motivo'), 'Trámite');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar bloqueo' }));

    await waitFor(() =>
      expect(body).toEqual({
        worker: 'worker-1',
        branch: null,
        starts_at: '2026-11-21T13:00:00.000Z',
        ends_at: '2026-11-21T14:00:00.000Z',
        reason: 'Trámite',
      }),
    );
  });

  test('elimina una ausencia tras confirmar', async () => {
    let deleted = '';
    server.use(
      workersHandler(),
      http.get('http://api.test/api/v1/time-off/', () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [vacation] }),
      ),
      http.delete('http://api.test/api/v1/time-off/timeoff-1/', () => {
        deleted = 'timeoff-1';
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderSection('timeOff');

    await userEvent.click(
      await screen.findByRole('button', { name: 'Eliminar ausencia Vacaciones' }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar' }));

    await waitFor(() => expect(deleted).toBe('timeoff-1'));
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas para verificar que fallan**

Run: `cd web && npm run test -- src/features/team/ExceptionsSection.test.tsx`

Expected: FAIL porque `ExceptionsSection` no existe.

- [ ] **Step 3: Implementar el diálogo de ausencias y bloqueos**

`web/src/features/team/ExceptionDialog.tsx`:

```tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import { teamApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Select } from '../../components/ui/Field';
import { dateTimeLocalToISO, todayInZone } from '../../lib/dates';

const exceptionSchema = z
  .object({
    branch: z.string(),
    start_local: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/, 'Selecciona fecha y hora de inicio.'),
    end_local: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/, 'Selecciona fecha y hora de término.'),
    reason: z.string().trim().max(240, 'Máximo 240 caracteres.'),
  })
  .refine((values) => values.end_local > values.start_local, {
    message: 'El término debe ser posterior al inicio.',
    path: ['end_local'],
  });

type ExceptionFormValues = z.infer<typeof exceptionSchema>;

export function ExceptionDialog({
  kind,
  workerId,
  onOpenChange,
  onSaved,
}: {
  kind: 'timeOff' | 'blocked';
  workerId: string;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const { bootstrap } = useAuth();
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);
  const defaultTimezone = branches[0]?.timezone ?? 'America/Santiago';
  const today = todayInZone(defaultTimezone);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<ExceptionFormValues>({
    resolver: zodResolver(exceptionSchema),
    defaultValues: {
      branch: branches[0]?.id ?? '',
      start_local: `${today}T09:00`,
      end_local: `${today}T10:00`,
      reason: '',
    },
  });
  const selectedBranch = watch('branch');
  const timezone =
    branches.find((branch) => branch.id === selectedBranch)?.timezone ?? defaultTimezone;

  const mutation = useMutation({
    mutationFn: (values: ExceptionFormValues) => {
      const payload = {
        worker: workerId,
        branch: values.branch || null,
        starts_at: dateTimeLocalToISO(values.start_local, timezone),
        ends_at: dateTimeLocalToISO(values.end_local, timezone),
        reason: values.reason,
      };
      return kind === 'timeOff'
        ? teamApi.timeOff.create(payload)
        : teamApi.blockedSlots.create(payload);
    },
    onSuccess: () => {
      onSaved();
      onOpenChange(false);
    },
  });

  const onSubmit = handleSubmit((values) => {
    mutation.mutate(values);
  });

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onOpenChange(false);
      }}
      title={kind === 'timeOff' ? 'Nueva ausencia' : 'Nuevo bloqueo'}
      description={
        kind === 'timeOff'
          ? 'La ausencia quita cupos en el rango indicado, en una sucursal o en todas.'
          : 'El bloqueo ocupa la agenda del trabajador sin crear una reserva.'
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {mutation.error ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudo guardar el registro.'
            }
          />
        ) : null}

        <Field
          label="Sucursal"
          htmlFor="exception-branch"
          error={errors.branch?.message}
          hint={`Las horas se interpretan en la zona ${timezone}.`}
        >
          <Select id="exception-branch" {...register('branch')}>
            <option value="">Todas las sucursales</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </Select>
        </Field>

        <FormRow>
          <Field label="Inicio" htmlFor="exception-start" error={errors.start_local?.message}>
            <Input id="exception-start" type="datetime-local" {...register('start_local')} />
          </Field>
          <Field label="Término" htmlFor="exception-end" error={errors.end_local?.message}>
            <Input id="exception-end" type="datetime-local" {...register('end_local')} />
          </Field>
        </FormRow>

        <Field label="Motivo" htmlFor="exception-reason" error={errors.reason?.message}>
          <Input id="exception-reason" {...register('reason')} />
        </Field>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending} loadingLabel="Guardando…">
            {kind === 'timeOff' ? 'Guardar ausencia' : 'Guardar bloqueo'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
```

- [ ] **Step 4: Implementar la sección de ausencias y bloqueos**

`web/src/features/team/ExceptionsSection.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError } from '../../api/client';
import { teamApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import type { Paginated } from '../../api/types';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/Dialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Select } from '../../components/ui/Field';
import { Skeleton } from '../../components/ui/Skeleton';
import { formatDateTime, formatTime } from '../../lib/dates';
import { ExceptionDialog } from './ExceptionDialog';

type ExceptionItem = {
  id: string;
  worker: string;
  branch: string | null;
  starts_at: string;
  ends_at: string;
  reason: string;
};

type ExceptionRecord = {
  id: string;
  label: string;
};

type ExceptionsApi = {
  list: (params?: { worker?: string; page?: number }) => Promise<Paginated<ExceptionItem>>;
  create: (input: {
    worker: string;
    branch: string | null;
    starts_at: string;
    ends_at: string;
    reason: string;
  }) => Promise<ExceptionItem>;
  remove: (id: string) => Promise<void>;
};

const CONFIG = {
  timeOff: {
    title: 'Ausencias',
    description: 'Vacaciones, licencias y permisos que quitan cupos en la agenda.',
    addLabel: 'Nueva ausencia',
    emptyTitle: 'Sin ausencias',
    emptyDescription: 'No hay ausencias registradas para este trabajador.',
    dialogTitle: 'Eliminar ausencia',
    apiPath: 'time-off',
  },
  blocked: {
    title: 'Bloqueos',
    description: 'Bloqueos puntuales de la agenda del trabajador.',
    addLabel: 'Nuevo bloqueo',
    emptyTitle: 'Sin bloqueos',
    emptyDescription: 'No hay bloqueos registrados para este trabajador.',
    dialogTitle: 'Eliminar bloqueo',
    apiPath: 'blocked-slots',
  },
} as const;

export function ExceptionsSection({
  kind,
  workerId,
  onWorkerChange,
}: {
  kind: 'timeOff' | 'blocked';
  workerId: string;
  onWorkerChange: (workerId: string) => void;
}) {
  const { company, bootstrap, can } = useAuth();
  const queryClient = useQueryClient();
  const canWrite = can('workforce.write');
  const config = CONFIG[kind];

  const [dialogOpen, setDialogOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<ExceptionRecord | null>(null);

  const workersQuery = useQuery({
    queryKey: queryKeys.workers(company?.id ?? '', { active: true, page: 1 }),
    queryFn: () => teamApi.workers.list({ active: true, page: 1 }),
    enabled: Boolean(company),
  });
  const workers = workersQuery.data?.results ?? [];
  const selectedWorkerId = workerId || workers[0]?.id || '';

  const api = (kind === 'timeOff' ? teamApi.timeOff : teamApi.blockedSlots) as ExceptionsApi;
  const keyFactory = kind === 'timeOff' ? queryKeys.timeOff : queryKeys.blockedSlots;

  const query = useQuery({
    queryKey: keyFactory(company?.id ?? '', selectedWorkerId),
    queryFn: () => api.list({ worker: selectedWorkerId, page: 1 }),
    enabled: Boolean(company && selectedWorkerId),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.remove(id),
    onSuccess: () => {
      setPendingDelete(null);
      void queryClient.invalidateQueries({
        queryKey: [config.apiPath, company?.id ?? ''],
      });
    },
  });

  const timezoneFor = (branchId: string | null) => {
    if (!branchId) return bootstrap?.branches[0]?.timezone ?? 'America/Santiago';
    return (
      bootstrap?.branches.find((branch) => branch.id === branchId)?.timezone ??
      'America/Santiago'
    );
  };
  const branchName = (branchId: string | null) =>
    branchId
      ? bootstrap?.branches.find((branch) => branch.id === branchId)?.name ?? 'Sucursal'
      : 'Todas las sucursales';

  const items = query.data?.results ?? [];
  const removeError =
    remove.error instanceof ApiError
      ? remove.error.message
      : remove.error
        ? 'No se pudo eliminar el registro.'
        : null;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <Field label="Trabajador" htmlFor={`${kind}-worker`} className="w-full sm:w-72">
          <Select
            id={`${kind}-worker`}
            value={selectedWorkerId}
            onChange={(event) => onWorkerChange(event.target.value)}
          >
            {workers.map((worker) => (
              <option key={worker.id} value={worker.id}>
                {worker.display_name}
              </option>
            ))}
          </Select>
        </Field>
        {canWrite && selectedWorkerId ? (
          <Button onClick={() => setDialogOpen(true)}>{config.addLabel}</Button>
        ) : null}
      </div>

      <p className="mb-4 text-sm text-muted">{config.description}</p>

      {removeError ? <ErrorBanner message={removeError} /> : null}
      {query.isError ? (
        <ErrorBanner
          message={`No se pudieron cargar ${config.title.toLowerCase()}.`}
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {workersQuery.isPending || query.isPending ? <Skeleton rows={3} /> : null}

      {!workersQuery.isPending && workers.length === 0 ? (
        <EmptyState
          title="Sin trabajadores"
          description="Crea un trabajador en la pestaña Trabajadores para registrar este tipo de bloqueo."
        />
      ) : null}

      {query.isSuccess && items.length === 0 ? (
        <EmptyState title={config.emptyTitle} description={config.emptyDescription} />
      ) : null}

      {items.length > 0 ? (
        <ul className="divide-y divide-line rounded-lg border border-line bg-panel">
          {items.map((item) => {
            const timezone = timezoneFor(item.branch);
            return (
              <li
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-2 p-4 text-sm"
              >
                <div>
                  <p className="font-medium text-ink">
                    {formatDateTime(item.starts_at, timezone)} –{' '}
                    {formatTime(item.ends_at, timezone)}
                  </p>
                  <p className="text-xs text-muted">
                    {branchName(item.branch)} · {item.reason || 'Sin motivo'}
                  </p>
                </div>
                {canWrite ? (
                  <Button
                    variant="ghost"
                    aria-label={`Eliminar ${kind === 'timeOff' ? 'ausencia' : 'bloqueo'} ${item.reason || 'sin motivo'}`}
                    onClick={() =>
                      setPendingDelete({
                        id: item.id,
                        label: `${formatDateTime(item.starts_at, timezone)} – ${formatTime(item.ends_at, timezone)}`,
                      })
                    }
                  >
                    Eliminar
                  </Button>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}

      {dialogOpen ? (
        <ExceptionDialog
          kind={kind}
          workerId={selectedWorkerId}
          onOpenChange={(next) => {
            if (!next) setDialogOpen(false);
          }}
          onSaved={() => {
            void queryClient.invalidateQueries({
              queryKey: [config.apiPath, company?.id ?? ''],
            });
          }}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        onOpenChange={(next) => {
          if (!next) setPendingDelete(null);
        }}
        title={config.dialogTitle}
        description={
          pendingDelete
            ? `Se quitará el registro ${pendingDelete.label}. Los cupos volverán a estar disponibles.`
            : ''
        }
        confirmLabel="Eliminar"
        loading={remove.isPending}
        onConfirm={() => {
          if (pendingDelete) remove.mutate(pendingDelete.id);
        }}
      />
    </div>
  );
}

export function TimeOffSection(props: {
  workerId: string;
  onWorkerChange: (workerId: string) => void;
}) {
  return <ExceptionsSection kind="timeOff" {...props} />;
}

export function BlockedSlotsSection(props: {
  workerId: string;
  onWorkerChange: (workerId: string) => void;
}) {
  return <ExceptionsSection kind="blocked" {...props} />;
}
```

- [ ] **Step 5: Agregar las pestañas a la página de equipo**

En `web/src/features/team/TeamPage.tsx`:

```tsx
import { BlockedSlotsSection, TimeOffSection } from './ExceptionsSection';

type TeamTab = 'workers' | 'schedule' | 'timeoff' | 'blocked';

const TABS: { id: TeamTab; label: string }[] = [
  { id: 'workers', label: 'Trabajadores' },
  { id: 'schedule', label: 'Horario' },
  { id: 'timeoff', label: 'Ausencias' },
  { id: 'blocked', label: 'Bloqueos' },
];
```

```tsx
      <div role="tabpanel" id="team-panel-timeoff" aria-labelledby="team-tab-timeoff" hidden={tab !== 'timeoff'}>
        {tab === 'timeoff' ? (
          <TimeOffSection workerId={workerId} onWorkerChange={setWorkerId} />
        ) : null}
      </div>
      <div role="tabpanel" id="team-panel-blocked" aria-labelledby="team-tab-blocked" hidden={tab !== 'blocked'}>
        {tab === 'blocked' ? (
          <BlockedSlotsSection workerId={workerId} onWorkerChange={setWorkerId} />
        ) : null}
      </div>
```

- [ ] **Step 6: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test -- src/features/team
npm run build
npm run lint
```

Expected: 14 tests PASS (las 9 de la tarea 16 más las 5 de ausencias y bloqueos); build y lint sin errores.

- [ ] **Step 7: Validación visual**

- Crear una ausencia de un día completo con "Todas las sucursales" y otra en Providencia.
- Comprobar que el horario local se muestra en la zona de la sucursal.
- Crear un bloqueo de dos horas y verificar que la agenda ya no ofrece esos cupos.
- Probar término anterior al inicio y un motivo largo.
- Eliminar una ausencia y un bloqueo.
- Repetir en claro y oscuro y a 768 px.

- [ ] **Step 8: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/features/team
git commit -m "feat(web): add time off and blocked slots management"
```

---

### Task 18: Resumen de ventas y caja de solo lectura

**Files:**
- Create: `web/src/features/summary/SummaryPage.tsx`, `web/src/features/summary/SummaryPage.test.tsx`
- Modify: `web/src/app/router.tsx`

**Interfaces:**
- Consumes: `summaryApi`, `queryKeys`, `useAuth`, `todayInZone`, `shiftDate`, `formatDateLabel`, `formatDateTime`, `formatMoney`, `formatPercent`, UI components.
- Produces: `SummaryPage` con rango de últimos 7 días por defecto, filtro de sucursal, métricas de ventas y caja, tablas por día, método de pago, servicios principales, sesiones de caja y gastos por categoría. Solo lectura.

- [ ] **Step 1: Escribir las pruebas del resumen**

`web/src/features/summary/SummaryPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import type { CashSummary, SalesSummary } from '../../api/summary';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { SummaryPage } from './SummaryPage';

const salesSummary: SalesSummary = {
  range: {
    date_from: '2026-11-05',
    date_to: '2026-11-11',
    timezone: 'America/Santiago',
    branch: null,
  },
  totals: {
    sales: 2,
    subtotal: '105000',
    discounts: '5000',
    total: '100000',
    paid: '100000',
    cost: '40000',
    profit: '60000',
    margin_percent: '60.00',
    average_ticket: '50000',
  },
  by_payment_method: [
    { method: 'cash', method_display: 'Efectivo', count: 1, amount: '60000' },
  ],
  by_day: [
    {
      date: '2026-11-11',
      sales: 2,
      subtotal: '105000',
      discounts: '5000',
      total: '100000',
      cost: '40000',
      profit: '60000',
    },
  ],
  by_branch: [
    {
      branch: 'branch-1',
      branch_name: 'Providencia',
      sales: 2,
      subtotal: '105000',
      discounts: '5000',
      total: '100000',
      cost: '40000',
    },
  ],
  top_products: [
    {
      product: 'product-1',
      description: 'Shampoo',
      sku: 'SH-01',
      quantity: '1.000',
      total: '10000',
      cost: '4000',
      profit: '6000',
    },
  ],
  top_services: [
    {
      service: 'service-1',
      description: 'Corte de cabello',
      sku: null,
      quantity: '2.000',
      total: '100000',
      cost: '40000',
      profit: '60000',
    },
  ],
};

const cashSummary: CashSummary = {
  range: {
    date_from: '2026-11-05',
    date_to: '2026-11-11',
    timezone: 'America/Santiago',
    branch: null,
  },
  totals: {
    sessions: 1,
    open: 0,
    closed: 1,
    opening: '20000',
    cash_sales: '60000',
    cash_expenses: '5000',
    expected: '75000',
    closing: '75000',
    difference: '0',
    expenses: '5000',
  },
  sessions: [
    {
      id: 'session-1',
      number: 'CJ-001',
      branch: 'branch-1',
      branch_name: 'Providencia',
      status: 'closed',
      opened_at: '2026-11-11T12:00:00Z',
      closed_at: '2026-11-11T21:00:00Z',
      opening_amount: '20000',
      cash_sales: '60000',
      cash_expenses: '5000',
      expected: '75000',
      closing_amount: '75000',
      difference: '0',
    },
  ],
  expenses_by_category: [{ category: 'Insumos', total: '5000' }],
  expenses_by_method: [{ method: 'cash', method_display: 'Efectivo', total: '5000' }],
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <SummaryPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function summaryHandlers(urls: { sales: string[]; cash: string[] }) {
  return [
    http.get('http://api.test/api/v1/reports/sales-summary/', ({ request }) => {
      urls.sales.push(request.url);
      return HttpResponse.json(salesSummary);
    }),
    http.get('http://api.test/api/v1/reports/cash-summary/', ({ request }) => {
      urls.cash.push(request.url);
      return HttpResponse.json(cashSummary);
    }),
  ];
}

describe('SummaryPage', () => {
  test('muestra totales de ventas del rango por defecto', async () => {
    const urls = { sales: [] as string[], cash: [] as string[] };
    server.use(...summaryHandlers(urls));
    renderPage();

    expect(await screen.findByText('Corte de cabello')).toBeInTheDocument();
    expect(screen.getAllByText('$ 100.000').length).toBeGreaterThan(0);
    expect(screen.getAllByText('$ 60.000').length).toBeGreaterThan(0);
    expect(screen.getByText('60 %')).toBeInTheDocument();
    expect(screen.getAllByText('Efectivo').length).toBeGreaterThan(0);
    expect(screen.getByText('Shampoo')).toBeInTheDocument();
    expect(screen.getAllByText('Providencia').length).toBeGreaterThan(1);

    expect(urls.sales).toHaveLength(1);
    expect(urls.sales[0]).toContain('date_from=');
    expect(urls.sales[0]).toContain('date_to=');
    expect(urls.sales[0]).not.toContain('branch=');
  });

  test('filtra por sucursal', async () => {
    const urls = { sales: [] as string[], cash: [] as string[] };
    server.use(...summaryHandlers(urls));
    renderPage();

    await screen.findByText('Corte de cabello');
    await userEvent.selectOptions(screen.getByLabelText('Sucursal'), 'branch-1');

    await waitFor(() => expect(urls.sales.length).toBe(2));
    expect(urls.sales[1]).toContain('branch=branch-1');
    expect(urls.cash[1]).toContain('branch=branch-1');
  });

  test('muestra caja, sesiones y gastos por categoría', async () => {
    const urls = { sales: [] as string[], cash: [] as string[] };
    server.use(...summaryHandlers(urls));
    renderPage();

    expect(await screen.findByText('CJ-001')).toBeInTheDocument();
    expect(screen.getByText('Cerrada')).toBeInTheDocument();
    expect(screen.getByText('Insumos')).toBeInTheDocument();
    expect(screen.getAllByText('$ 75.000').length).toBeGreaterThan(0);
    expect(urls.cash).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas para verificar que fallan**

Run: `cd web && npm run test -- src/features/summary/SummaryPage.test.tsx`

Expected: FAIL porque `SummaryPage` no existe.

- [ ] **Step 3: Implementar la página de resumen**

`web/src/features/summary/SummaryPage.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { queryKeys } from '../../api/queryKeys';
import { summaryApi } from '../../api/runtime';
import type { SummaryParams } from '../../api/summary';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select } from '../../components/ui/Field';
import { PageHeader } from '../../components/ui/PageHeader';
import { Skeleton } from '../../components/ui/Skeleton';
import { shiftDate, todayInZone, formatDateLabel } from '../../lib/dates';
import { formatMoney, formatPercent } from '../../lib/format';

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-panel p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold text-ink">{value}</p>
    </div>
  );
}

export function SummaryPage() {
  const { company, bootstrap } = useAuth();
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);
  const [branchId, setBranchId] = useState('');
  const timezone = branches.find((branch) => branch.id === branchId)?.timezone
    ?? branches[0]?.timezone
    ?? 'America/Santiago';
  const [dateTo, setDateTo] = useState(() => todayInZone(timezone));
  const [dateFrom, setDateFrom] = useState(() => shiftDate(todayInZone(timezone), -6));

  const rangeValid = Boolean(dateFrom && dateTo && dateFrom <= dateTo);
  const params: SummaryParams = {
    date_from: dateFrom,
    date_to: dateTo,
    branch: branchId || undefined,
  };

  const salesQuery = useQuery({
    queryKey: queryKeys.salesSummary(company?.id ?? '', params),
    queryFn: () => summaryApi.sales(params),
    enabled: Boolean(company) && rangeValid,
  });
  const cashQuery = useQuery({
    queryKey: queryKeys.cashSummary(company?.id ?? '', params),
    queryFn: () => summaryApi.cash(params),
    enabled: Boolean(company) && rangeValid,
  });

  const sales = salesQuery.data;
  const cash = cashQuery.data;

  return (
    <section>
      <PageHeader
        title="Resumen"
        description="Ventas y caja de la empresa para el rango y la sucursal seleccionados."
      />

      <div className="mb-6 grid gap-3 sm:grid-cols-3">
        <Field label="Desde" htmlFor="summary-from">
          <Input
            id="summary-from"
            type="date"
            max={dateTo}
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
          />
        </Field>
        <Field label="Hasta" htmlFor="summary-to">
          <Input
            id="summary-to"
            type="date"
            min={dateFrom}
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
          />
        </Field>
        <Field label="Sucursal" htmlFor="summary-branch">
          <Select
            id="summary-branch"
            value={branchId}
            onChange={(event) => setBranchId(event.target.value)}
          >
            <option value="">Todas las sucursales</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      {!rangeValid ? (
        <ErrorBanner message="La fecha desde no puede ser posterior a la fecha hasta." />
      ) : null}

      <section aria-labelledby="summary-sales-heading" className="mb-8">
        <h2 id="summary-sales-heading" className="mb-3 text-lg font-semibold text-ink">
          Ventas
        </h2>

        {salesQuery.isError ? (
          <ErrorBanner
            message="No se pudo cargar el resumen de ventas."
            onRetry={() => void salesQuery.refetch()}
          />
        ) : null}
        {salesQuery.isPending && rangeValid ? <Skeleton rows={3} /> : null}

        {sales ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <Metric label="Total vendido" value={formatMoney(sales.totals.total)} />
              <Metric label="Pagado" value={formatMoney(sales.totals.paid)} />
              <Metric label="Ganancia" value={formatMoney(sales.totals.profit)} />
              <Metric label="Margen" value={formatPercent(sales.totals.margin_percent)} />
              <Metric label="Ticket promedio" value={formatMoney(sales.totals.average_ticket)} />
              <Metric label="Reservas" value={String(sales.totals.sales)} />
            </div>

            <div className="mt-5 grid gap-5 lg:grid-cols-2">
              <div className="rounded-lg border border-line bg-panel">
                <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                  Ventas por día
                </h3>
                {sales.by_day.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-muted">Sin ventas en el rango.</p>
                ) : (
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs uppercase tracking-wide text-muted">
                      <tr>
                        <th scope="col" className="px-4 py-2">Día</th>
                        <th scope="col" className="px-4 py-2">Reservas</th>
                        <th scope="col" className="px-4 py-2 text-right">Total</th>
                        <th scope="col" className="px-4 py-2 text-right">Ganancia</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {sales.by_day.map((day) => (
                        <tr key={day.date}>
                          <td className="px-4 py-2 text-ink">{formatDateLabel(day.date)}</td>
                          <td className="px-4 py-2 text-muted">{day.sales}</td>
                          <td className="px-4 py-2 text-right text-muted">
                            {formatMoney(day.total)}
                          </td>
                          <td className="px-4 py-2 text-right text-muted">
                            {formatMoney(day.profit)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="rounded-lg border border-line bg-panel">
                <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                  Por método de pago
                </h3>
                {sales.by_payment_method.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-muted">Sin pagos en el rango.</p>
                ) : (
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs uppercase tracking-wide text-muted">
                      <tr>
                        <th scope="col" className="px-4 py-2">Método</th>
                        <th scope="col" className="px-4 py-2">Cantidad</th>
                        <th scope="col" className="px-4 py-2 text-right">Monto</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {sales.by_payment_method.map((row) => (
                        <tr key={row.method}>
                          <td className="px-4 py-2 text-ink">{row.method_display}</td>
                          <td className="px-4 py-2 text-muted">{row.count}</td>
                          <td className="px-4 py-2 text-right text-muted">
                            {formatMoney(row.amount)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            <div className="mt-5 grid gap-5 lg:grid-cols-2">
              <div className="rounded-lg border border-line bg-panel">
                <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                  Ventas por sucursal
                </h3>
                {sales.by_branch.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-muted">Sin ventas por sucursal en el rango.</p>
                ) : (
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs uppercase tracking-wide text-muted">
                      <tr>
                        <th scope="col" className="px-4 py-2">Sucursal</th>
                        <th scope="col" className="px-4 py-2">Reservas</th>
                        <th scope="col" className="px-4 py-2 text-right">Total</th>
                        <th scope="col" className="px-4 py-2 text-right">Costo</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {sales.by_branch.map((row) => (
                        <tr key={row.branch}>
                          <td className="px-4 py-2 text-ink">{row.branch_name}</td>
                          <td className="px-4 py-2 text-muted">{row.sales}</td>
                          <td className="px-4 py-2 text-right text-muted">
                            {formatMoney(row.total)}
                          </td>
                          <td className="px-4 py-2 text-right text-muted">
                            {formatMoney(row.cost)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="rounded-lg border border-line bg-panel">
                <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                  Productos más vendidos
                </h3>
                {sales.top_products.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-muted">Sin productos vendidos en el rango.</p>
                ) : (
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs uppercase tracking-wide text-muted">
                      <tr>
                        <th scope="col" className="px-4 py-2">Producto</th>
                        <th scope="col" className="px-4 py-2">SKU</th>
                        <th scope="col" className="px-4 py-2">Cantidad</th>
                        <th scope="col" className="px-4 py-2 text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {sales.top_products.map((item) => (
                        <tr key={item.product ?? item.description}>
                          <td className="px-4 py-2 text-ink">{item.description}</td>
                          <td className="px-4 py-2 text-muted">{item.sku ?? '—'}</td>
                          <td className="px-4 py-2 text-muted">{item.quantity}</td>
                          <td className="px-4 py-2 text-right text-muted">
                            {formatMoney(item.total)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            <div className="mt-5 rounded-lg border border-line bg-panel">
              <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                Servicios más vendidos
              </h3>
              {sales.top_services.length === 0 ? (
                <p className="px-4 py-6 text-sm text-muted">Sin servicios vendidos en el rango.</p>
              ) : (
                <table className="w-full text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-muted">
                    <tr>
                      <th scope="col" className="px-4 py-2">Servicio</th>
                      <th scope="col" className="px-4 py-2">Cantidad</th>
                      <th scope="col" className="px-4 py-2 text-right">Total</th>
                      <th scope="col" className="px-4 py-2 text-right">Ganancia</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {sales.top_services.map((item) => (
                      <tr key={item.service ?? item.description}>
                        <td className="px-4 py-2 text-ink">{item.description}</td>
                        <td className="px-4 py-2 text-muted">{item.quantity}</td>
                        <td className="px-4 py-2 text-right text-muted">
                          {formatMoney(item.total)}
                        </td>
                        <td className="px-4 py-2 text-right text-muted">
                          {formatMoney(item.profit)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        ) : null}
      </section>

      <section aria-labelledby="summary-cash-heading">
        <h2 id="summary-cash-heading" className="mb-3 text-lg font-semibold text-ink">
          Caja
        </h2>

        {cashQuery.isError ? (
          <ErrorBanner
            message="No se pudo cargar el resumen de caja."
            onRetry={() => void cashQuery.refetch()}
          />
        ) : null}
        {cashQuery.isPending && rangeValid ? <Skeleton rows={3} /> : null}

        {cash ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <Metric label="Sesiones" value={String(cash.totals.sessions)} />
              <Metric label="Esperado" value={formatMoney(cash.totals.expected)} />
              <Metric label="Contado" value={formatMoney(cash.totals.closing)} />
              <Metric label="Diferencia" value={formatMoney(cash.totals.difference)} />
              <Metric label="Gastos" value={formatMoney(cash.totals.expenses)} />
            </div>

            <div className="mt-5 overflow-x-auto rounded-lg border border-line bg-panel">
              <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                Sesiones de caja
              </h3>
              {cash.sessions.length === 0 ? (
                <p className="px-4 py-6 text-sm text-muted">Sin sesiones en el rango.</p>
              ) : (
                <table className="w-full text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-muted">
                    <tr>
                      <th scope="col" className="px-4 py-2">Número</th>
                      <th scope="col" className="px-4 py-2">Sucursal</th>
                      <th scope="col" className="px-4 py-2">Estado</th>
                      <th scope="col" className="px-4 py-2 text-right">Apertura</th>
                      <th scope="col" className="px-4 py-2 text-right">Esperado</th>
                      <th scope="col" className="px-4 py-2 text-right">Cierre</th>
                      <th scope="col" className="px-4 py-2 text-right">Diferencia</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {cash.sessions.map((session) => (
                      <tr key={session.id}>
                        <td className="px-4 py-2 font-medium text-ink">{session.number}</td>
                        <td className="px-4 py-2 text-muted">{session.branch_name}</td>
                        <td className="px-4 py-2">
                          <Badge tone={session.status === 'open' ? 'active' : 'inactive'}>
                            {session.status === 'open' ? 'Abierta' : 'Cerrada'}
                          </Badge>
                        </td>
                        <td className="px-4 py-2 text-right text-muted">
                          {formatMoney(session.opening_amount)}
                        </td>
                        <td className="px-4 py-2 text-right text-muted">
                          {formatMoney(session.expected)}
                        </td>
                        <td className="px-4 py-2 text-right text-muted">
                          {formatMoney(session.closing_amount)}
                        </td>
                        <td className="px-4 py-2 text-right text-muted">
                          {session.difference === null ? '—' : formatMoney(session.difference)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="mt-5 rounded-lg border border-line bg-panel">
              <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                Gastos por categoría
              </h3>
              {cash.expenses_by_category.length === 0 ? (
                <p className="px-4 py-6 text-sm text-muted">Sin gastos en el rango.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {cash.expenses_by_category.map((row) => (
                    <li key={row.category} className="flex justify-between px-4 py-2 text-sm">
                      <span className="text-ink">{row.category}</span>
                      <span className="text-muted">{formatMoney(row.total)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="mt-5 rounded-lg border border-line bg-panel">
              <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                Gastos por método
              </h3>
              {cash.expenses_by_method.length === 0 ? (
                <p className="px-4 py-6 text-sm text-muted">Sin gastos por método en el rango.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {cash.expenses_by_method.map((row) => (
                    <li key={row.method} className="flex justify-between px-4 py-2 text-sm">
                      <span className="text-ink">{row.method_display}</span>
                      <span className="text-muted">{formatMoney(row.total)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        ) : null}
      </section>

      {sales && cash && sales.totals.sales === 0 && cash.totals.sessions === 0 ? (
        <EmptyState
          title="Sin movimientos"
          description="No hay ventas ni sesiones de caja en el rango seleccionado."
        />
      ) : null}
    </section>
  );
}
```

- [ ] **Step 4: Reemplazar la ruta de resumen**

En `web/src/app/router.tsx`, importar `SummaryPage` y reemplazar el placeholder:

```tsx
import { SummaryPage } from '../features/summary/SummaryPage';
```

```tsx
      {
        path: 'resumen',
        element: (
          <RequirePermission permission="reports.read">
            <SummaryPage />
          </RequirePermission>
        ),
      },
```

- [ ] **Step 5: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test -- src/features/summary
npm run build
npm run lint
```

Expected: 3 tests PASS; build y lint sin errores.

- [ ] **Step 6: Validación visual**

- Abrir el resumen y comprobar el rango de 7 días con la sucursal "Todas".
- Cambiar a Providencia y verificar que las cifras coinciden con la API para el mismo rango.
- Cambiar fechas a un rango sin datos y comprobar los estados vacíos.
- Probar "Desde" posterior a "Hasta": aparece el aviso y no hay consultas nuevas.
- Comprobar que los montos y porcentajes usan formato chileno.
- Repetir en claro y oscuro y a 768 px; la tabla de sesiones debe desplazarse horizontalmente sin romper el layout.

- [ ] **Step 7: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/features/summary web/src/app/router.tsx
git commit -m "feat(web): add read-only sales and cash summary"
```

---

### Task 19: Editor de marca con vista previa y logo

**Files:**
- Create: `web/src/features/branding/BrandingPage.tsx`, `web/src/features/branding/BrandingPage.test.tsx`
- Modify: `web/src/app/router.tsx`

**Interfaces:**
- Consumes: `brandingApi`, `queryKeys`, `useAuth().refreshBootstrap`, `readableForeground`, `ApiError`, UI components.
- Produces: `BrandingPage` con formulario de nombre, identificador, colores y tema; vista previa en vivo; subida y eliminación de logo; aviso cuando cambia el identificador. Al guardar refresca el bootstrap para que el tema y el nombre se apliquen en todo el panel.

- [ ] **Step 1: Escribir las pruebas de marca**

`web/src/features/branding/BrandingPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test, vi } from 'vitest';

import type { Branding } from '../../api/branding';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { BrandingPage } from './BrandingPage';

const branding: Branding = {
  display_name: 'Estudio Aurora',
  logo_url: '/media/logo.png',
  primary_color: '#10B981',
  secondary_color: '#065F46',
  theme_mode: 'light',
  booking_url: '/b/estudio-aurora/',
  name: 'Estudio Aurora',
  slug: 'estudio-aurora',
  can_manage: true,
};

function renderPage(refreshBootstrap = vi.fn().mockResolvedValue(undefined)) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue({ refreshBootstrap })}>
      <QueryClientProvider client={queryClient}>
        <BrandingPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
  return { refreshBootstrap };
}

function brandingHandler(payload: Branding = branding) {
  return http.get('http://api.test/api/v1/company/branding/', () => HttpResponse.json(payload));
}

describe('BrandingPage', () => {
  test('muestra la marca actual y la vista previa', async () => {
    server.use(brandingHandler());
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Vista previa' })).toBeInTheDocument();
    expect(screen.getAllByText('Estudio Aurora').length).toBeGreaterThan(0);
    expect(screen.getByText('/b/estudio-aurora/')).toBeInTheDocument();
    expect(screen.getByAltText('Logo de Estudio Aurora')).toHaveAttribute(
      'src',
      '/media/logo.png',
    );
  });

  test('guarda la marca y refresca el bootstrap', async () => {
    let body: unknown;
    server.use(
      brandingHandler(),
      http.patch('http://api.test/api/v1/company/branding/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...branding, display_name: 'Aurora Studio' });
      }),
    );
    const { refreshBootstrap } = renderPage();

    await screen.findByRole('heading', { name: 'Vista previa' });
    await userEvent.clear(screen.getByLabelText('Nombre visible'));
    await userEvent.type(screen.getByLabelText('Nombre visible'), 'Aurora Studio');
    await userEvent.selectOptions(screen.getByLabelText('Tema'), 'dark');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() =>
      expect(body).toMatchObject({
        display_name: 'Aurora Studio',
        slug: 'estudio-aurora',
        primary_color: '#10B981',
        secondary_color: '#065F46',
        theme_mode: 'dark',
      }),
    );
    expect(await screen.findByText('Marca actualizada.')).toBeInTheDocument();
    expect(refreshBootstrap).toHaveBeenCalled();
  });

  test('muestra el error del identificador ocupado', async () => {
    server.use(
      brandingHandler(),
      http.patch('http://api.test/api/v1/company/branding/', () =>
        HttpResponse.json(
          { slug: ['Este identificador de empresa ya está ocupado.'] },
          { status: 400 },
        ),
      ),
    );
    renderPage();

    await screen.findByRole('heading', { name: 'Vista previa' });
    await userEvent.clear(screen.getByLabelText('Identificador'));
    await userEvent.type(screen.getByLabelText('Identificador'), 'aurora');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    expect(
      await screen.findByText('Este identificador de empresa ya está ocupado.'),
    ).toBeInTheDocument();
  });

  test('sube un logo como multipart', async () => {
    let uploaded: File | null = null;
    server.use(
      brandingHandler(),
      http.post('http://api.test/api/v1/company/branding/logo/', async ({ request }) => {
        const form = await request.formData();
        uploaded = form.get('logo') as File;
        return HttpResponse.json({ ...branding, logo_url: '/media/logo-nuevo.png' });
      }),
    );
    renderPage();

    await screen.findByRole('heading', { name: 'Vista previa' });
    const file = new File(['png'], 'logo-nuevo.png', { type: 'image/png' });
    await userEvent.upload(screen.getByLabelText('Logo'), file);
    await userEvent.click(screen.getByRole('button', { name: 'Subir logo' }));

    await waitFor(() => expect(uploaded?.name).toBe('logo-nuevo.png'));
  });

  test('elimina el logo actual', async () => {
    let removed = false;
    server.use(
      brandingHandler(),
      http.delete('http://api.test/api/v1/company/branding/logo/', () => {
        removed = true;
        return HttpResponse.json({ ...branding, logo_url: '' });
      }),
    );
    renderPage();

    await screen.findByRole('heading', { name: 'Vista previa' });
    await userEvent.click(screen.getByRole('button', { name: 'Quitar logo' }));

    await waitFor(() => expect(removed).toBe(true));
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas para verificar que fallan**

Run: `cd web && npm run test -- src/features/branding/BrandingPage.test.tsx`

Expected: FAIL porque `BrandingPage` no existe.

- [ ] **Step 3: Implementar la página de marca**

`web/src/features/branding/BrandingPage.tsx`:

```tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import type { Branding, BrandingInput } from '../../api/branding';
import { brandingApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Select } from '../../components/ui/Field';
import { PageHeader } from '../../components/ui/PageHeader';
import { Skeleton } from '../../components/ui/Skeleton';
import { readableForeground } from '../../lib/colors';

const brandingSchema = z.object({
  display_name: z.string().trim().max(180, 'Máximo 180 caracteres.'),
  slug: z
    .string()
    .trim()
    .min(1, 'Ingresa el identificador.')
    .max(100, 'Máximo 100 caracteres.')
    .regex(/^[a-z0-9_-]+$/i, 'Usa letras, números, guiones o guiones bajos.'),
  primary_color: z
    .string()
    .regex(/^#[0-9A-Fa-f]{6}$/, 'Usa un color hexadecimal con formato #RRGGBB.'),
  secondary_color: z
    .string()
    .regex(/^#[0-9A-Fa-f]{6}$/, 'Usa un color hexadecimal con formato #RRGGBB.'),
  theme_mode: z.enum(['light', 'dark']),
});

type BrandingFormValues = z.infer<typeof brandingSchema>;

const LOGO_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const MAX_LOGO_BYTES = 2 * 1024 * 1024;

function valuesFrom(branding: Branding): BrandingFormValues {
  return {
    display_name: branding.display_name,
    slug: branding.slug,
    primary_color: branding.primary_color,
    secondary_color: branding.secondary_color,
    theme_mode: branding.theme_mode,
  };
}

function BrandingForm({ branding }: { branding: Branding }) {
  const { company, refreshBootstrap } = useAuth();
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState(false);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoError, setLogoError] = useState('');

  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors },
  } = useForm<BrandingFormValues>({
    resolver: zodResolver(brandingSchema),
    defaultValues: valuesFrom(branding),
  });
  const values = watch();
  const slugChanged = values.slug !== branding.slug;

  const refresh = async () => {
    await refreshBootstrap();
    void queryClient.invalidateQueries({ queryKey: queryKeys.branding(company?.id ?? '') });
  };

  const save = useMutation({
    mutationFn: (input: BrandingInput) => brandingApi.update(input),
    onSuccess: async () => {
      setSaved(true);
      await refresh();
    },
    onError: (error) => {
      setSaved(false);
      if (!(error instanceof ApiError) || !error.fields) return;
      (['display_name', 'slug', 'primary_color', 'secondary_color'] as const).forEach((field) => {
        const messages = error.fields?.[field];
        if (messages) setError(field, { message: messages[0] });
      });
    },
  });

  const uploadLogo = useMutation({
    mutationFn: (file: File) => brandingApi.uploadLogo(file),
    onSuccess: async () => {
      setLogoFile(null);
      setLogoError('');
      await refresh();
    },
  });

  const removeLogo = useMutation({
    mutationFn: () => brandingApi.removeLogo(),
    onSuccess: refresh,
  });

  const onSubmit = handleSubmit((formValues) => {
    save.mutate({ ...formValues, slug: formValues.slug.toLowerCase() });
  });

  const previewForeground = readableForeground(values.primary_color);
  const previewSurface = values.theme_mode === 'dark' ? '#0b1220' : '#f8fafc';
  const previewText = values.theme_mode === 'dark' ? '#f8fafc' : '#0f172a';

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {saved ? (
          <p role="status" className="rounded-md bg-success-soft px-4 py-3 text-sm text-success">
            Marca actualizada.
          </p>
        ) : null}
        {save.error && !(save.error instanceof ApiError && save.error.fields) ? (
          <ErrorBanner
            message={
              save.error instanceof ApiError
                ? save.error.message
                : 'No se pudo guardar la marca.'
            }
          />
        ) : null}

        <FormRow>
          <Field
            label="Nombre visible"
            htmlFor="branding-display-name"
            error={errors.display_name?.message}
            hint="Si queda vacío se usa el nombre legal de la empresa."
          >
            <Input id="branding-display-name" {...register('display_name')} />
          </Field>
          <Field
            label="Identificador"
            htmlFor="branding-slug"
            error={errors.slug?.message}
            hint="Define la dirección de la página pública."
          >
            <Input id="branding-slug" {...register('slug')} />
          </Field>
        </FormRow>

        {slugChanged ? (
          <p role="status" className="rounded-md bg-warning-soft px-4 py-3 text-sm text-warning">
            Cambiar el identificador modifica el enlace público. Los enlaces anteriores dejarán de
            funcionar.
          </p>
        ) : null}

        <FormRow>
          <Field label="Color primario" htmlFor="branding-primary" error={errors.primary_color?.message}>
            <div className="flex items-center gap-3">
              <input
                id="branding-primary"
                type="color"
                className="h-10 w-16 rounded-md border border-line bg-panel p-1"
                {...register('primary_color')}
              />
              <span className="text-sm text-muted">{values.primary_color}</span>
            </div>
          </Field>
          <Field
            label="Color secundario"
            htmlFor="branding-secondary"
            error={errors.secondary_color?.message}
          >
            <div className="flex items-center gap-3">
              <input
                id="branding-secondary"
                type="color"
                className="h-10 w-16 rounded-md border border-line bg-panel p-1"
                {...register('secondary_color')}
              />
              <span className="text-sm text-muted">{values.secondary_color}</span>
            </div>
          </Field>
        </FormRow>

        <Field label="Tema" htmlFor="branding-theme" error={errors.theme_mode?.message}>
          <Select id="branding-theme" {...register('theme_mode')}>
            <option value="light">Claro</option>
            <option value="dark">Oscuro</option>
          </Select>
        </Field>

        <div className="flex justify-end pt-2">
          <Button type="submit" loading={save.isPending} loadingLabel="Guardando…">
            Guardar cambios
          </Button>
        </div>

        <fieldset className="rounded-lg border border-line bg-panel p-4">
          <legend className="px-1 text-sm font-medium text-ink">Logo de la empresa</legend>
          <div className="flex flex-wrap items-center gap-4">
            {branding.logo_url ? (
              <img
                src={branding.logo_url}
                alt={`Logo de ${branding.display_name}`}
                className="h-16 w-16 rounded-md border border-line object-contain"
              />
            ) : (
              <div className="flex h-16 w-16 items-center justify-center rounded-md border border-dashed border-line text-xs text-muted">
                Sin logo
              </div>
            )}
            <div className="min-w-0 flex-1 space-y-2">
              <Field label="Logo" htmlFor="branding-logo" error={logoError}>
                <Input
                  id="branding-logo"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(event) => {
                    const file = event.target.files?.[0] ?? null;
                    setLogoFile(null);
                    setLogoError('');
                    if (!file) return;
                    if (!LOGO_TYPES.includes(file.type)) {
                      setLogoError('Usa PNG, JPEG o WebP.');
                      return;
                    }
                    if (file.size > MAX_LOGO_BYTES) {
                      setLogoError('El logo no puede superar 2 MB.');
                      return;
                    }
                    setLogoFile(file);
                  }}
                />
              </Field>
              <p className="text-xs text-muted">
                PNG, JPEG o WebP de hasta 2 MB y 4000 × 4000 px.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={!logoFile}
                  loading={uploadLogo.isPending}
                  loadingLabel="Subiendo…"
                  onClick={() => {
                    if (logoFile) uploadLogo.mutate(logoFile);
                  }}
                >
                  Subir logo
                </Button>
                {branding.logo_url ? (
                  <Button
                    type="button"
                    variant="ghost"
                    loading={removeLogo.isPending}
                    loadingLabel="Quitando…"
                    onClick={() => removeLogo.mutate()}
                  >
                    Quitar logo
                  </Button>
                ) : null}
              </div>
              {uploadLogo.error || removeLogo.error ? (
                <ErrorBanner
                  message={
                    uploadLogo.error instanceof ApiError
                      ? uploadLogo.error.message
                      : removeLogo.error instanceof ApiError
                        ? removeLogo.error.message
                        : 'No se pudo actualizar el logo.'
                  }
                />
              ) : null}
            </div>
          </div>
        </fieldset>
      </form>

      <aside className="rounded-lg border border-line bg-panel p-4">
        <h2 className="mb-3 text-base font-semibold text-ink">Vista previa</h2>
        <div className="rounded-lg p-4" style={{ backgroundColor: previewSurface, color: previewText }}>
          <div
            className="rounded-lg p-4"
            style={{ backgroundColor: values.primary_color, color: previewForeground }}
          >
            <p className="text-xs uppercase tracking-wide opacity-80">Página pública</p>
            <p className="mt-1 text-lg font-semibold">{values.display_name || branding.name}</p>
            <p className="mt-3 text-sm">Reserva tu hora en línea.</p>
            <span
              className="mt-4 inline-flex rounded-md px-3 py-2 text-xs font-semibold"
              style={{
                backgroundColor: values.secondary_color,
                color: readableForeground(values.secondary_color),
              }}
            >
              Reservar ahora
            </span>
          </div>
        </div>
        <p className="mt-3 text-xs text-muted">Enlace público actual</p>
        <p className="break-all text-sm text-ink">{branding.booking_url}</p>
        {slugChanged ? (
          <p className="mt-2 break-all text-xs text-muted">Nuevo enlace: /b/{values.slug}/</p>
        ) : null}
      </aside>
    </div>
  );
}

export function BrandingPage() {
  const { company } = useAuth();
  const query = useQuery({
    queryKey: queryKeys.branding(company?.id ?? ''),
    queryFn: () => brandingApi.get(),
    enabled: Boolean(company),
  });

  return (
    <section>
      <PageHeader
        title="Marca"
        description="Nombre, colores, tema y logo que se aplican al panel y a la página pública."
      />
      {query.isError ? (
        <ErrorBanner
          message="No se pudo cargar la marca."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {query.isPending ? <Skeleton rows={5} /> : null}
      {query.data ? <BrandingForm branding={query.data} /> : null}
    </section>
  );
}
```

- [ ] **Step 4: Reemplazar la ruta de marca**

En `web/src/app/router.tsx`, importar `BrandingPage` y reemplazar el placeholder:

```tsx
import { BrandingPage } from '../features/branding/BrandingPage';
```

```tsx
      {
        path: 'marca',
        element: (
          <RequirePermission permission="company.manage">
            <BrandingPage />
          </RequirePermission>
        ),
      },
```

- [ ] **Step 5: Eliminar el placeholder**

Verificar que `PlaceholderPage` ya no se usa en `router.tsx` y borrar `web/src/app/PlaceholderPage.tsx`:

Run:

```bash
cd web
grep -rn "PlaceholderPage" src || true
```

Expected: sin resultados. Si no hay referencias, eliminar el archivo:

```bash
rm web/src/app/PlaceholderPage.tsx
```

- [ ] **Step 6: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test -- src/features/branding
npm run test
npm run build
npm run lint
```

Expected: 5 tests PASS; la suite completa queda verde; build y lint sin errores.

- [ ] **Step 7: Validación visual**

- Guardar un nombre nuevo y comprobar que la barra lateral, el menú y la página pública muestran el cambio sin recargar.
- Cambiar los colores y verificar el contraste del texto del botón en claro y oscuro.
- Cambiar el identificador y comprobar el aviso y el nuevo enlace público tras guardar.
- Subir un PNG menor a 2 MB; ver la vista previa del logo.
- Intentar un PDF y un archivo mayor a 2 MB; el formulario muestra el error local.
- Quitar el logo y verificar que desaparece de la vista previa y del panel.
- Repetir en claro y oscuro y a 768 px.

- [ ] **Step 8: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/features/branding web/src/app/router.tsx
git rm web/src/app/PlaceholderPage.tsx
git commit -m "feat(web): add branding editor with live preview and logo"
```

---

### Task 19A: Inventario de solo lectura

**Files:**
- Modify: `web/src/api/client.ts`, `web/src/api/client.test.ts`, `web/src/api/queryKeys.ts`, `web/src/api/runtime.ts`, `web/src/app/router.tsx`, `web/src/lib/permissions.ts`
- Create: `web/src/api/inventory.ts`, `web/src/features/inventory/InventoryPage.tsx`, `web/src/features/inventory/InventoryObjectsTab.tsx`, `web/src/features/inventory/InventoryFilesTab.tsx`, `web/src/features/inventory/InventoryPage.test.tsx`

**Interfaces:**
- Consumes: `ApiClient`, `Paginated`, `UUID`, `queryKeys`, `inventoryApi`, `useAuth`, `useDebouncedValue`, `Field`, `Input`, `Select`, `Pagination`, `Skeleton`, `EmptyState`, `ErrorBanner`, `formatDateLabel`.
- Produces:
  - `ApiClient.download(path, query?)` → `{ blob, filename }` con el mismo refresh único y la misma normalización de errores que `request`.
  - `createInventoryApi(client)` con `listAssets`, `listDocuments`, `downloadDocument`, `productPhoto`; tipos `InventoryProduct`, `InventoryDocument`, `AssetStatus`, `AssetListParams`, `DocumentListParams`.
  - `InventoryPage` con pestañas Objetos y Archivos, sin acciones de escritura.
  - Ruta `/inventario` con `inventory.read` y entrada de navegación con la feature `inventory`.

El backend de inventario (productos con `kind=asset`, documentos, foto y descarga autenticada) viene del plan `docs/superpowers/plans/2026-11-11-inventario-objetos-archivos.md`. Esta tarea solo consume esos endpoints y no crea, edita ni elimina nada. La descarga usa `fetch` con los encabezados tenant y se entrega como blob; nunca se construye una URL pública ni se usa `<a href>` directo al endpoint protegido.

- [ ] **Step 1: Escribir las pruebas de descarga y de la pantalla**

Agregar al final de `web/src/api/client.test.ts`, dentro de `describe('ApiClient', ...)`:

```ts
  test('descarga binarios y lee el nombre del archivo', async () => {
    server.use(
      http.get('http://api.test/api/v1/inventory/documents/document-1/download/', () =>
        new HttpResponse(new Blob(['%PDF-1.4'], { type: 'application/pdf' }), {
          headers: {
            'Content-Type': 'application/pdf',
            'Content-Disposition': 'attachment; filename="factura.pdf"',
          },
        }),
      ),
    );

    const result = await makeClient().download(
      '/api/v1/inventory/documents/document-1/download/',
    );

    expect(result.filename).toBe('factura.pdf');
    expect(result.blob.type).toBe('application/pdf');
    expect(result.blob.size).toBeGreaterThan(0);
  });
```

`web/src/features/inventory/InventoryPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue, makeBootstrap } from '../../test/factories';
import { server } from '../../test/server';
import { InventoryPage } from './InventoryPage';

const assetFixture = {
  id: 'product-1',
  company: 'company-a',
  kind: 'asset',
  kind_display: 'Objeto',
  status: 'available',
  status_display: 'Disponible',
  sku: 'ACT-1A2B3C4D',
  name: 'Máquina de corte',
  description: '',
  category: null,
  category_name: null,
  unit: 'unit',
  unit_display: 'Unidad',
  cost: '150000.00',
  price: '0.00',
  reorder_point: '0.000',
  barcode: '',
  branch: 'branch-1',
  branch_name: 'Providencia',
  assigned_worker: 'worker-1',
  assigned_worker_name: 'Paula Rojas',
  serial_number: 'SN-001',
  internal_code: 'INT-01',
  quantity: 1,
  purchase_date: '2025-05-10',
  supplier: null,
  supplier_name: null,
  warranty_until: '2027-05-10',
  notes: '',
  photo_url: '/api/v1/inventory/products/product-1/photo/',
  photo_content_type: 'image/png',
  photo_size: 1024,
  active: true,
  created_at: '2026-11-11T12:00:00Z',
  updated_at: '2026-11-11T12:00:00Z',
};

const documentFixture = {
  id: 'document-1',
  company: 'company-a',
  client_id: null,
  name: 'Factura máquina',
  original_name: 'factura.pdf',
  content_type: 'application/pdf',
  size: 128734,
  product: 'product-1',
  product_name: 'Máquina de corte',
  product_sku: 'ACT-1A2B3C4D',
  uploaded_by_email: 'dueno@example.com',
  download_url: '/api/v1/inventory/documents/document-1/download/',
  created_at: '2026-11-11T15:00:00Z',
  updated_at: '2026-11-11T15:00:00Z',
};

function inventoryAuth(permissions: string[] = ['inventory.read']) {
  const base = makeBootstrap();
  return makeAuthValue({
    bootstrap: makeBootstrap({
      permissions,
      features: { ...base.features, inventory: true },
      modules: { ...base.modules, inventory: true },
    }),
  });
}

function renderInventory(permissions?: string[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={inventoryAuth(permissions)}>
      <QueryClientProvider client={queryClient}>
        <InventoryPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function useInventoryHandlers(urls: string[] = [], documentCount = 1) {
  server.use(
    http.get('http://api.test/api/v1/inventory/products/', ({ request }) => {
      urls.push(request.url);
      return HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [assetFixture],
      });
    }),
    http.get(
      'http://api.test/api/v1/inventory/products/product-1/photo/',
      () =>
        new HttpResponse(new Blob(['png'], { type: 'image/png' }), {
          headers: { 'Content-Type': 'image/png' },
        }),
    ),
    http.get('http://api.test/api/v1/inventory/documents/', ({ request }) => {
      urls.push(request.url);
      return HttpResponse.json({
        count: documentCount,
        next: null,
        previous: null,
        results: [documentFixture],
      });
    }),
    http.get(
      'http://api.test/api/v1/inventory/documents/document-1/download/',
      () =>
        new HttpResponse(new Blob(['%PDF-1.4'], { type: 'application/pdf' }), {
          headers: {
            'Content-Type': 'application/pdf',
            'Content-Disposition': 'attachment; filename="factura.pdf"',
          },
        }),
    ),
  );
}

describe('InventoryPage', () => {
  beforeEach(() => {
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:inventario'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  });

  afterEach(() => vi.restoreAllMocks());

  test('lista los objetos activos de la empresa', async () => {
    const urls: string[] = [];
    useInventoryHandlers(urls);
    renderInventory();

    expect(await screen.findByText('Máquina de corte')).toBeInTheDocument();
    expect(screen.getByText('ACT-1A2B3C4D')).toBeInTheDocument();
    expect(screen.getByText('Paula Rojas')).toBeInTheDocument();
    expect(urls[0]).toContain('kind=asset');
    expect(urls[0]).toContain('active=true');
  });

  test('descarga un archivo como blob autenticado', async () => {
    useInventoryHandlers();
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {});
    renderInventory();
    await screen.findByText('Máquina de corte');
    vi.mocked(URL.createObjectURL).mockClear();

    await userEvent.click(screen.getByRole('tab', { name: 'Archivos' }));
    await userEvent.click(
      await screen.findByRole('button', { name: 'Descargar Factura máquina' }),
    );

    await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
    const blobs = vi.mocked(URL.createObjectURL).mock.calls.map(([value]) => value as Blob);
    expect(blobs.some((blob) => blob.type === 'application/pdf')).toBe(true);
  });

  test('filtra objetos por búsqueda y sucursal', async () => {
    const urls: string[] = [];
    useInventoryHandlers(urls);
    renderInventory();
    await screen.findByText('Máquina de corte');

    await userEvent.type(screen.getByLabelText('Buscar objeto'), 'maquina');
    await waitFor(() => expect(urls.at(-1)).toContain('search=maquina'));

    await userEvent.selectOptions(screen.getByLabelText('Sucursal'), 'branch-1');
    await waitFor(() => expect(urls.at(-1)).toContain('branch=branch-1'));
  });

  test('pagina la lista de archivos', async () => {
    const urls: string[] = [];
    useInventoryHandlers(urls, 120);
    renderInventory();
    await userEvent.click(screen.getByRole('tab', { name: 'Archivos' }));
    await screen.findByText('Factura máquina');

    const pagination = screen.getByRole('navigation', { name: 'Paginación' });
    await userEvent.click(within(pagination).getByRole('button', { name: 'Siguiente' }));

    await waitFor(() => expect(urls.at(-1)).toContain('page=2'));
  });

  test('sin permiso no consulta ni muestra datos', async () => {
    const urls: string[] = [];
    useInventoryHandlers(urls);
    renderInventory([]);

    expect(screen.getByText('Sin acceso a inventario')).toBeInTheDocument();
    expect(urls).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

Run:

```bash
cd web
npm run test -- src/api/client.test.ts src/features/inventory
```

Expected: FAIL porque `download` y la pantalla no existen.

- [ ] **Step 3: Agregar descarga binaria al cliente**

En `web/src/api/client.ts`, ampliar `RequestOptions` con el tipo de contenido aceptado:

```ts
export type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  formData?: FormData;
  query?: QueryParams;
  auth?: boolean;
  retry?: boolean;
  accept?: string;
};
```

Agregar esta función antes de `export class ApiClient`:

```ts
function filenameFromDisposition(header: string | null): string | null {
  if (!header) return null;
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1].trim());
    } catch {
      return encoded[1].trim();
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain ? plain[1].trim() : null;
}
```

Reemplazar el método `request` completo por estos tres métodos y mover el cuerpo actual a `send`:

```ts
  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const response = await this.send(path, options);
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  async download(
    path: string,
    query?: QueryParams,
  ): Promise<{ blob: Blob; filename: string | null }> {
    const response = await this.send(path, { query, accept: '*/*' });
    return {
      blob: await response.blob(),
      filename: filenameFromDisposition(response.headers.get('Content-Disposition')),
    };
  }

  private async send(path: string, options: RequestOptions = {}): Promise<Response> {
    const {
      method = 'GET',
      body,
      formData,
      query,
      auth = true,
      retry = true,
      accept = 'application/json',
    } = options;
    const origin = this.baseUrl || window.location.origin;
    const url = new URL(`${origin}${path}`);
    Object.entries(query ?? {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    });

    const headers: Record<string, string> = { Accept: accept };
    if (body !== undefined && !formData) headers['Content-Type'] = 'application/json';
    if (auth) {
      const access = this.getAccessToken();
      if (access) headers.Authorization = `Bearer ${access}`;
      const contextId = this.getTenantContextId();
      if (contextId) headers['X-Tenant-Context'] = contextId;
    }

    let response: Response;
    try {
      response = await this.fetchImpl(url.toString(), {
        method,
        headers,
        body: formData ?? (body === undefined ? undefined : JSON.stringify(body)),
      });
    } catch {
      throw normalizeError(0, null);
    }

    if (response.status === 401 && auth && retry) {
      try {
        await this.refreshOnce();
      } catch {
        this.unauthorizedHandler?.();
        throw new ApiError(401, 'Sesión expirada.');
      }
      return this.send(path, { ...options, retry: false });
    }

    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw normalizeError(response.status, payload);
    }

    return response;
  }
```

`request` conserva el manejo de 204 y el resto del comportamiento; las pruebas existentes deben seguir pasando sin cambios. Si el servidor no expone `Content-Disposition` por CORS, `filename` será `null` y la interfaz usará `original_name`.

- [ ] **Step 4: Implementar el cliente de inventario**

`web/src/api/inventory.ts`:

```ts
import type { ApiClient } from './client';
import type { Paginated, UUID } from './types';

export type AssetStatus = 'available' | 'assigned' | 'maintenance' | 'retired';

export type InventoryProduct = {
  id: UUID;
  company: UUID;
  kind: 'asset';
  kind_display: string;
  status: AssetStatus;
  status_display: string;
  sku: string;
  name: string;
  description: string;
  category: UUID | null;
  category_name: string | null;
  unit: string;
  unit_display: string;
  cost: string;
  price: string;
  reorder_point: string;
  barcode: string;
  branch: UUID | null;
  branch_name: string | null;
  assigned_worker: UUID | null;
  assigned_worker_name: string;
  serial_number: string;
  internal_code: string;
  quantity: number;
  purchase_date: string | null;
  supplier: UUID | null;
  supplier_name: string | null;
  warranty_until: string | null;
  notes: string;
  photo_url: string;
  photo_content_type: string;
  photo_size: number;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type InventoryDocument = {
  id: UUID;
  company: UUID;
  client_id: UUID | null;
  name: string;
  original_name: string;
  content_type: string;
  size: number;
  product: UUID | null;
  product_name: string | null;
  product_sku: string | null;
  uploaded_by_email: string | null;
  download_url: string;
  created_at: string;
  updated_at: string;
};

export type AssetListParams = {
  search?: string;
  branch?: UUID;
  status?: AssetStatus;
  active?: boolean;
  page?: number;
};

export type DocumentListParams = {
  search?: string;
  linked?: boolean;
  product?: UUID;
  page?: number;
};

export function createInventoryApi(client: ApiClient) {
  return {
    listAssets: (params: AssetListParams = {}) =>
      client.get<Paginated<InventoryProduct>>('/api/v1/inventory/products/', {
        ...params,
        kind: 'asset',
      }),
    listDocuments: (params: DocumentListParams = {}) =>
      client.get<Paginated<InventoryDocument>>('/api/v1/inventory/documents/', {
        ...params,
      }),
    downloadDocument: (file: Pick<InventoryDocument, 'download_url'>) =>
      client.download(file.download_url),
    productPhoto: (path: string) => client.download(path),
  };
}

export type InventoryApi = ReturnType<typeof createInventoryApi>;
```

En `web/src/api/queryKeys.ts`, importar los tipos y agregar las claves:

```ts
import type { AssetListParams, DocumentListParams } from './inventory';
```

```ts
  inventoryProducts: (companyId: UUID, params: AssetListParams) =>
    list('inventory-products', companyId, params),
  inventoryDocuments: (companyId: UUID, params: DocumentListParams) =>
    list('inventory-documents', companyId, params),
  inventoryPhoto: (companyId: UUID, productId: UUID) =>
    ['inventory-photo', companyId, productId] as const,
```

En `web/src/api/runtime.ts`, importar y exportar:

```ts
import { createInventoryApi } from './inventory';
```

```ts
export const inventoryApi = createInventoryApi(apiClient);
```

- [ ] **Step 5: Implementar la pantalla y las pestañas**

`web/src/features/inventory/InventoryPage.tsx`:

```tsx
import { useState } from 'react';

import { useAuth } from '../../auth/AuthProvider';
import { EmptyState } from '../../components/ui/EmptyState';
import { PageHeader } from '../../components/ui/PageHeader';
import { InventoryFilesTab } from './InventoryFilesTab';
import { InventoryObjectsTab } from './InventoryObjectsTab';

const TABS = [
  { value: 'objects', label: 'Objetos' },
  { value: 'files', label: 'Archivos' },
] as const;

type TabValue = (typeof TABS)[number]['value'];

export function InventoryPage() {
  const { can } = useAuth();
  const [tab, setTab] = useState<TabValue>('objects');

  if (!can('inventory.read')) {
    return (
      <EmptyState
        title="Sin acceso a inventario"
        description="Tu rol no tiene permiso para consultar objetos ni archivos de la empresa."
      />
    );
  }

  return (
    <section>
      <PageHeader
        title="Inventario"
        description="Objetos y archivos de la empresa. La gestión se realiza desde la aplicación móvil."
      />

      <div role="tablist" aria-label="Inventario" className="mb-4 flex gap-2 border-b border-line">
        {TABS.map((item) => (
          <button
            key={item.value}
            type="button"
            role="tab"
            id={`inventory-tab-${item.value}`}
            aria-selected={tab === item.value}
            aria-controls={`inventory-panel-${item.value}`}
            tabIndex={tab === item.value ? 0 : -1}
            onClick={() => setTab(item.value)}
            onKeyDown={(event) => {
              if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
              event.preventDefault();
              const index = TABS.findIndex((entry) => entry.value === tab);
              const nextIndex =
                event.key === 'ArrowRight'
                  ? (index + 1) % TABS.length
                  : (index - 1 + TABS.length) % TABS.length;
              const next = TABS[nextIndex];
              setTab(next.value);
              window.document.getElementById(`inventory-tab-${next.value}`)?.focus();
            }}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand ${
              tab === item.value
                ? 'border-brand text-brand'
                : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <section
        role="tabpanel"
        id="inventory-panel-objects"
        aria-labelledby="inventory-tab-objects"
        hidden={tab !== 'objects'}
      >
        <InventoryObjectsTab />
      </section>
      <section
        role="tabpanel"
        id="inventory-panel-files"
        aria-labelledby="inventory-tab-files"
        hidden={tab !== 'files'}
      >
        <InventoryFilesTab />
      </section>
    </section>
  );
}
```

`web/src/features/inventory/InventoryObjectsTab.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import type { AssetStatus, InventoryProduct } from '../../api/inventory';
import { queryKeys } from '../../api/queryKeys';
import { inventoryApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select } from '../../components/ui/Field';
import { Pagination } from '../../components/ui/Pagination';
import { Skeleton } from '../../components/ui/Skeleton';
import { formatDateLabel } from '../../lib/dates';
import { useDebouncedValue } from '../../lib/useDebouncedValue';

const STATUS_OPTIONS: { value: AssetStatus | ''; label: string }[] = [
  { value: '', label: 'Todos los estados' },
  { value: 'available', label: 'Disponible' },
  { value: 'assigned', label: 'Asignado' },
  { value: 'maintenance', label: 'En mantenimiento' },
  { value: 'retired', label: 'Dado de baja' },
];

function AssetPhoto({ product }: { product: InventoryProduct }) {
  const { company } = useAuth();
  const [url, setUrl] = useState<string | null>(null);
  const photoQuery = useQuery({
    queryKey: queryKeys.inventoryPhoto(company?.id ?? '', product.id),
    queryFn: () => inventoryApi.productPhoto(product.photo_url),
    enabled: Boolean(company && product.photo_url),
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (!photoQuery.data) {
      setUrl(null);
      return;
    }
    const objectUrl = URL.createObjectURL(photoQuery.data.blob);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [photoQuery.data]);

  const fallback = (
    <span
      aria-hidden="true"
      className="flex h-10 w-10 items-center justify-center rounded-md bg-surface text-sm font-semibold text-muted"
    >
      {product.name.slice(0, 1).toUpperCase()}
    </span>
  );

  if (!product.photo_url || photoQuery.isError) {
    return fallback;
  }

  if (url) {
    return (
      <img
        src={url}
        alt={`Foto de ${product.name}`}
        className="h-10 w-10 rounded-md object-cover"
      />
    );
  }

  return <span aria-hidden="true" className="block h-10 w-10 animate-pulse rounded-md bg-line" />;
}

export function InventoryObjectsTab() {
  const { company, bootstrap } = useAuth();
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);
  const [search, setSearch] = useState('');
  const [branchId, setBranchId] = useState('');
  const [status, setStatus] = useState<AssetStatus | ''>('');
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebouncedValue(search, 300);

  useEffect(() => {
    setPage(1);
  }, [company?.id]);

  const params = {
    search: debouncedSearch || undefined,
    branch: branchId || undefined,
    status: status || undefined,
    active: true,
    page,
  };
  const query = useQuery({
    queryKey: queryKeys.inventoryProducts(company?.id ?? '', params),
    queryFn: () => inventoryApi.listAssets(params),
    enabled: Boolean(company),
  });
  const products = query.data?.results ?? [];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-2">
        <Field
          label="Buscar objeto"
          htmlFor="inventory-object-search"
          className="min-w-[220px]"
        >
          <Input
            id="inventory-object-search"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Nombre, SKU o código de barras"
          />
        </Field>

        <Field label="Sucursal" htmlFor="inventory-object-branch">
          <Select
            id="inventory-object-branch"
            value={branchId}
            onChange={(event) => {
              setBranchId(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Todas</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Estado" htmlFor="inventory-object-status">
          <Select
            id="inventory-object-status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as AssetStatus | '');
              setPage(1);
            }}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      {query.isError ? (
        <ErrorBanner
          message={
            query.error instanceof Error ? query.error.message : 'No se pudo cargar el inventario.'
          }
          onRetry={() => void query.refetch()}
        />
      ) : query.isLoading ? (
        <Skeleton rows={5} />
      ) : products.length === 0 ? (
        <EmptyState
          title="Sin objetos registrados"
          description="Los objetos se crean desde la aplicación móvil y aparecen aquí para consulta."
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="p-3">Objeto</th>
                  <th scope="col" className="p-3">Estado</th>
                  <th scope="col" className="p-3">Sucursal</th>
                  <th scope="col" className="p-3">Responsable</th>
                  <th scope="col" className="p-3">Serie</th>
                  <th scope="col" className="p-3">Garantía</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {products.map((product) => (
                  <tr key={product.id}>
                    <td className="p-3">
                      <div className="flex items-center gap-3">
                        <AssetPhoto product={product} />
                        <div>
                          <p className="font-medium text-ink">{product.name}</p>
                          <p className="text-xs text-muted">{product.sku}</p>
                        </div>
                      </div>
                    </td>
                    <td className="p-3 text-ink">{product.status_display}</td>
                    <td className="p-3 text-ink">{product.branch_name || 'Sin sucursal'}</td>
                    <td className="p-3 text-ink">
                      {product.assigned_worker_name || 'Sin asignar'}
                    </td>
                    <td className="p-3 text-ink">{product.serial_number || '—'}</td>
                    <td className="p-3 text-ink">
                      {product.warranty_until ? formatDateLabel(product.warranty_until) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {query.data ? (
            <Pagination page={page} count={query.data.count} onPage={setPage} />
          ) : null}
        </>
      )}
    </div>
  );
}
```

`web/src/features/inventory/InventoryFilesTab.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import type { InventoryDocument } from '../../api/inventory';
import { queryKeys } from '../../api/queryKeys';
import { inventoryApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select } from '../../components/ui/Field';
import { Pagination } from '../../components/ui/Pagination';
import { Skeleton } from '../../components/ui/Skeleton';
import { useDebouncedValue } from '../../lib/useDebouncedValue';

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  const units = ['KB', 'MB', 'GB'];
  let size = value / 1024;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  const formatted = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 1 }).format(size);
  return `${formatted} ${units[unit]}`;
}

export function InventoryFilesTab() {
  const { company } = useAuth();
  const [search, setSearch] = useState('');
  const [linked, setLinked] = useState<'' | 'true' | 'false'>('');
  const [page, setPage] = useState(1);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const debouncedSearch = useDebouncedValue(search, 300);

  useEffect(() => {
    setPage(1);
  }, [company?.id]);

  const params = {
    search: debouncedSearch || undefined,
    linked: linked === '' ? undefined : linked === 'true',
    page,
  };
  const query = useQuery({
    queryKey: queryKeys.inventoryDocuments(company?.id ?? '', params),
    queryFn: () => inventoryApi.listDocuments(params),
    enabled: Boolean(company),
  });
  const documents = query.data?.results ?? [];

  async function download(file: InventoryDocument) {
    setDownloading(file.id);
    setDownloadError(null);
    try {
      const result = await inventoryApi.downloadDocument(file);
      const objectUrl = URL.createObjectURL(result.blob);
      const anchor = window.document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = result.filename ?? file.original_name;
      window.document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
    } catch (error) {
      setDownloadError(
        error instanceof Error ? error.message : 'No se pudo descargar el archivo.',
      );
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-2">
        <Field label="Buscar archivo" htmlFor="inventory-file-search" className="min-w-[220px]">
          <Input
            id="inventory-file-search"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Nombre o nombre original"
          />
        </Field>

        <Field label="Vínculo" htmlFor="inventory-file-linked">
          <Select
            id="inventory-file-linked"
            value={linked}
            onChange={(event) => {
              setLinked(event.target.value as '' | 'true' | 'false');
              setPage(1);
            }}
          >
            <option value="">Todos</option>
            <option value="true">Vinculados a un objeto</option>
            <option value="false">Sin vínculo</option>
          </Select>
        </Field>
      </div>

      {downloadError ? <ErrorBanner message={downloadError} /> : null}

      {query.isError ? (
        <ErrorBanner
          message={
            query.error instanceof Error ? query.error.message : 'No se pudieron cargar los archivos.'
          }
          onRetry={() => void query.refetch()}
        />
      ) : query.isLoading ? (
        <Skeleton rows={5} />
      ) : documents.length === 0 ? (
        <EmptyState
          title="Sin archivos"
          description="Los archivos se suben desde la aplicación móvil. Aquí puedes consultarlos y descargarlos."
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="p-3">Archivo</th>
                  <th scope="col" className="p-3">Vínculo</th>
                  <th scope="col" className="p-3">Tamaño</th>
                  <th scope="col" className="p-3">Subido por</th>
                  <th scope="col" className="p-3">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {documents.map((file) => (
                  <tr key={file.id}>
                    <td className="p-3">
                      <p className="font-medium text-ink">{file.name}</p>
                      <p className="text-xs text-muted">{file.original_name}</p>
                    </td>
                    <td className="p-3 text-ink">
                      {file.product_name ?? 'Sin vínculo'}
                      {file.product_sku ? (
                        <span className="block text-xs text-muted">{file.product_sku}</span>
                      ) : null}
                    </td>
                    <td className="p-3 text-ink">{formatBytes(file.size)}</td>
                    <td className="p-3 text-ink">{file.uploaded_by_email ?? '—'}</td>
                    <td className="p-3">
                      <button
                        type="button"
                        aria-label={`Descargar ${file.name}`}
                        disabled={downloading === file.id}
                        onClick={() => void download(file)}
                        className="rounded-md border border-line bg-panel px-3 py-1.5 text-sm font-medium text-ink transition hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {downloading === file.id ? 'Descargando…' : 'Descargar'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {query.data ? (
            <Pagination page={page} count={query.data.count} onPage={setPage} />
          ) : null}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Registrar la ruta y la navegación**

En `web/src/lib/permissions.ts`, agregar la entrada después de Equipo:

```ts
  { path: '/inventario', label: 'Inventario', permission: 'inventory.read', feature: 'inventory' },
```

En `web/src/app/router.tsx`, importar y registrar la ruta antes de `resumen`:

```tsx
import { InventoryPage } from '../features/inventory/InventoryPage';
```

```tsx
      {
        path: 'inventario',
        element: (
          <RequirePermission permission="inventory.read">
            <InventoryPage />
          </RequirePermission>
        ),
      },
```

- [ ] **Step 7: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test
npm run build
npm run lint
```

Expected: la suite completa pasa (incluye 1 prueba nueva del cliente y 5 de inventario); build y lint sin errores.

- [ ] **Step 8: Validación visual**

Con el backend local y una empresa con `inventory` habilitado, revisar en 1280 px y 768 px, claro y oscuro:

- La entrada Inventario aparece solo con `inventory.read` y la feature activa.
- Objetos muestra foto, nombre, estado, sucursal y responsable; los filtros actualizan la lista.
- Archivos muestra nombre, vínculo y tamaño; descargar abre el archivo con su nombre original.
- Sin permiso, la ruta redirige a acceso restringido y la pantalla no muestra datos.
- Las tablas se desplazan horizontalmente sin romper el layout; los botones y pestañas son operables con teclado y foco visible.
- Cambiar de empresa vuelve a la primera página y no conserva filas de la empresa anterior.

- [ ] **Step 9: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/api web/src/features/inventory web/src/app/router.tsx web/src/lib/permissions.ts
git commit -m "feat(web): add read-only inventory of objects and files"
```

---

### Task 19B: Calendario semanal con eje horario y alta desde hueco

**Files:**
- Modify: `web/src/api/queryKeys.ts`, `web/src/features/agenda/agendaLayout.ts`, `web/src/features/agenda/agendaLayout.test.ts`, `web/src/features/agenda/AgendaCalendar.tsx`, `web/src/features/agenda/AgendaPage.tsx`, `web/src/features/agenda/AgendaPage.test.tsx`, `web/src/features/agenda/BookingCreateDialog.tsx`, `web/src/features/agenda/BookingCreateDialog.test.tsx`

**Interfaces:**
- Consumes: `WorkingHours` de `api/team`, `teamApi.workingHours.list`, `todayInZone`, `formatDateLabel`, `isoToDateTimeLocal`, `weekRange`, `shiftDate`.
- Produces:
  - `hourBounds(bookings, timeZone, shifts?, weekdays?)` con horario de atención y respaldo 08:00–20:00.
  - `weekdayIndex`, `slotStepMinutes`, `slotStarts`, `timeLabel`, `slotBlockStyle`, `CalendarSlot` y `CALENDAR_HOUR_HEIGHT` en `agendaLayout.ts`.
  - `AgendaCalendar` con eje horario alineado en Semana, huecos clicables en Día y Semana, y `onSelectSlot`.
  - `BookingCreateDialog` con `initialSlot` que fija día y hora y, cuando el hueco viene de una columna de trabajador, también lo preselecciona; luego marca el cupo exacto de disponibilidad.
  - `queryKeys.branchWorkingHours(companyId, branchId)`.

El eje usa el horario de atención de la sucursal cuando `GET /api/v1/working-hours/?branch=<id>` responde; ese endpoint exige `workforce.read` y la feature `workforce`. Los roles dueño, administrador, gerente y recepción tienen `workforce.read`; recepción igual recibe `403` si el plan contratado no incluye `workforce`, y un trabajador con `bookings.own.read` recibe `403` siempre. En todos esos casos el calendario usa 08:00–20:00 como respaldo, sin bloquear la agenda. Los huecos solo abren el alta; el servidor sigue siendo la autoridad de disponibilidad.

- [ ] **Step 1: Escribir las pruebas del eje, de los huecos y de la precarga**

Agregar al final de `web/src/features/agenda/agendaLayout.test.ts`, dentro de `describe('agendaLayout', ...)`:

```ts
  test('usa el horario de atención de la sucursal cuando existe', () => {
    const shift: WorkingHours = {
      id: 'hours-1',
      worker: 'worker-1',
      branch: 'branch-1',
      weekday: 0,
      start_time: '09:00:00',
      end_time: '18:00:00',
    };
    expect(hourBounds([], 'America/Santiago', [shift], [0])).toEqual({
      startHour: 9,
      endHour: 18,
    });
  });

  test('ignora los turnos de días que no están a la vista', () => {
    const shift: WorkingHours = {
      id: 'hours-1',
      worker: 'worker-1',
      branch: 'branch-1',
      weekday: 0,
      start_time: '09:00:00',
      end_time: '18:00:00',
    };
    expect(hourBounds([], 'America/Santiago', [shift], [5])).toEqual({
      startHour: 8,
      endHour: 20,
    });
  });

  test('interpreta el fin a medianoche como 24:00', () => {
    const shift: WorkingHours = {
      id: 'hours-1',
      worker: 'worker-1',
      branch: 'branch-1',
      weekday: 0,
      start_time: '18:00:00',
      end_time: '00:00:00',
    };
    expect(hourBounds([], 'America/Santiago', [shift], [0])).toEqual({
      startHour: 18,
      endHour: 24,
    });
  });

  test('amplía el eje por reservas fuera del horario de atención', () => {
    const early = booking({
      start_at: '2026-01-15T10:00:00Z',
      end_at: '2026-01-15T10:30:00Z',
    });
    const shift: WorkingHours = {
      id: 'hours-1',
      worker: 'worker-1',
      branch: 'branch-1',
      weekday: 3,
      start_time: '09:00:00',
      end_time: '18:00:00',
    };
    expect(hourBounds([early], 'America/Santiago', [shift], [3])).toEqual({
      startHour: 7,
      endHour: 18,
    });
  });

  test('calcula días, franjas y etiquetas del calendario', () => {
    expect(weekdayIndex('2026-01-12')).toBe(0);
    expect(weekdayIndex('2026-01-18')).toBe(6);
    expect(slotStepMinutes(8, 20)).toBe(30);
    expect(slotStepMinutes(0, 24)).toBe(60);
    expect(slotStarts(9, 10)).toEqual([540, 570]);
    expect(timeLabel(570)).toBe('09:30');
    expect(slotBlockStyle(570, 9, 10)).toEqual({ top: '50%', height: '50%' });
  });
```

Reemplazar el import existente de `./agendaLayout` por el que incluye los helpers nuevos (no agregar una segunda línea de import para el mismo módulo):

```ts
import type { WorkingHours } from '../../api/team';
import {
  bookingBlockStyle,
  groupWeek,
  hourBounds,
  slotBlockStyle,
  slotStarts,
  slotStepMinutes,
  timeLabel,
  weekdayIndex,
} from './agendaLayout';
```

Actualizar `useAgendaHandlers` en `AgendaPage.test.tsx` para responder los horarios y los clientes del diálogo:

```ts
    http.get('http://api.test/api/v1/working-hours/', () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
    http.get('http://api.test/api/v1/customers/', () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
```

Agregar la prueba después de la de vista semanal:

```tsx
  test('abre el alta con el día, la hora y el trabajador del hueco', async () => {
    useAgendaHandlers();
    const today = todayInZone('America/Santiago');
    server.use(
      http.get('http://api.test/api/v1/working-hours/', () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 'hours-1',
              worker: 'worker-1',
              branch: 'branch-1',
              weekday: weekdayIndex(today),
              start_time: '09:00:00',
              end_time: '18:00:00',
            },
          ],
        }),
      ),
    );
    renderAgenda();
    await screen.findByText(/Ana Díaz/);

    await userEvent.click(
      screen.getByRole('button', { name: /a las 10:00 con Paula Rojas$/ }),
    );

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByLabelText('Día')).toHaveValue(today);
    expect(within(dialog).getByLabelText('Trabajador')).toHaveValue('worker-1');
  });
```

Agregar a los imports de `AgendaPage.test.tsx`:

```ts
import { todayInZone } from '../../lib/dates';
import { weekdayIndex } from './agendaLayout';
```

y `within` desde `@testing-library/react`.

Actualizar `renderDialog` en `BookingCreateDialog.test.tsx` para aceptar el hueco:

```tsx
import type { CalendarSlot } from './agendaLayout';

function renderDialog(open = true, initialSlot: CalendarSlot | null = null) {
```

y pasar `initialSlot={initialSlot}` al diálogo. Agregar la prueba:

```tsx
  test('preselecciona el horario y el trabajador solicitados', async () => {
    server.use(...baseHandlers);
    renderDialog(true, { date: '2026-11-12', time: '10:30', workerId: 'worker-1' });

    await screen.findByRole('option', { name: 'Paula Rojas' });
    expect(screen.getByLabelText('Trabajador')).toHaveValue('worker-1');
    await userEvent.selectOptions(screen.getByLabelText('Servicio'), 'service-1');

    const slot = await screen.findByRole('button', { name: '10:30' });
    await waitFor(() => expect(slot).toHaveAttribute('aria-pressed', 'true'));
  });
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

Run:

```bash
cd web
npm run test -- src/features/agenda
```

Expected: FAIL porque `hourBounds` no acepta horarios, no existen los helpers de franjas y el calendario no emite huecos.

- [ ] **Step 3: Extender el cálculo de la agenda**

En `web/src/features/agenda/agendaLayout.ts`, agregar el import del tipo y reemplazar `hourBounds` por la versión con horarios de atención:

```ts
import type { WorkingHours } from '../../api/team';
```

```ts
export const CALENDAR_HOUR_HEIGHT = 64;

export type CalendarSlot = { date: string; time: string; workerId?: string };

export function weekdayIndex(dateISO: string): number {
  const [year, month, day] = dateISO.split('-').map(Number);
  return (new Date(Date.UTC(year, month - 1, day)).getUTCDay() + 6) % 7;
}

function minutesOfTime(value: string): number {
  const [hour, minute] = value.split(':').map(Number);
  return (hour || 0) * 60 + (minute || 0);
}

export function hourBounds(
  bookings: Booking[],
  timeZone: string,
  shifts: WorkingHours[] = [],
  weekdays?: number[],
): { startHour: number; endHour: number } {
  const visible = weekdays && weekdays.length > 0 ? new Set(weekdays) : null;
  let shiftStart: number | null = null;
  let shiftEnd: number | null = null;
  shifts.forEach((shift) => {
    if (visible && !visible.has(shift.weekday)) return;
    const start = minutesOfTime(shift.start_time);
    const rawEnd = minutesOfTime(shift.end_time);
    const end = rawEnd === 0 ? 24 * 60 : rawEnd;
    if (end <= start) return;
    shiftStart = shiftStart === null ? start : Math.min(shiftStart, start);
    shiftEnd = shiftEnd === null ? end : Math.max(shiftEnd, end);
  });

  let startHour = shiftStart === null ? DEFAULT_START_HOUR : Math.floor(shiftStart / 60);
  let endHour = shiftEnd === null ? DEFAULT_END_HOUR : Math.ceil(shiftEnd / 60);
  bookings.forEach((booking) => {
    const start = localMinutes(booking.start_at, timeZone);
    const end = start + booking.duration_minutes;
    startHour = Math.min(startHour, Math.floor(start / 60));
    if (end > start) endHour = Math.max(endHour, Math.ceil(end / 60));
  });
  return {
    startHour: Math.max(0, startHour),
    endHour: Math.min(24, Math.max(startHour + 2, endHour)),
  };
}

export function slotStepMinutes(startHour: number, endHour: number): number {
  return endHour - startHour > 16 ? 60 : 30;
}

export function slotStarts(startHour: number, endHour: number): number[] {
  const step = slotStepMinutes(startHour, endHour);
  const total = (endHour - startHour) * 60;
  return Array.from({ length: Math.floor(total / step) }, (_, index) => startHour * 60 + index * step);
}

export function timeLabel(minutes: number): string {
  const hour = Math.floor(minutes / 60);
  const minute = minutes % 60;
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
}

export function slotBlockStyle(
  startMinutes: number,
  startHour: number,
  endHour: number,
): { top: string; height: string } {
  const total = (endHour - startHour) * 60;
  const step = slotStepMinutes(startHour, endHour);
  return {
    top: `${((startMinutes - startHour * 60) / total) * 100}%`,
    height: `${(step / total) * 100}%`,
  };
}
```

La firma con parámetros opcionales conserva las llamadas y pruebas existentes de la tarea 10.

- [ ] **Step 4: Reemplazar el calendario con eje y huecos**

`web/src/features/agenda/AgendaCalendar.tsx` (archivo completo):

```tsx
import type { Booking } from '../../api/agenda';
import type { Worker, WorkingHours } from '../../api/team';
import { formatDateLabel, formatTime } from '../../lib/dates';
import {
  CALENDAR_HOUR_HEIGHT,
  bookingBlockStyle,
  bookingsForWorker,
  groupWeek,
  hourBounds,
  slotBlockStyle,
  slotStarts,
  timeLabel,
  weekdayIndex,
  type CalendarSlot,
} from './agendaLayout';

type Props = {
  view: 'day' | 'week';
  anchorDate: string;
  dateFrom: string;
  timezone: string;
  workers: Worker[];
  bookings: Booking[];
  shifts?: WorkingHours[];
  onSelectBooking: (booking: Booking) => void;
  onSelectSlot?: (slot: CalendarSlot) => void;
};

function workerColor(worker: Worker): string {
  return /^#[0-9A-Fa-f]{6}$/.test(worker.color) ? worker.color : 'var(--brand-primary)';
}

export function AgendaCalendar({
  view,
  anchorDate,
  dateFrom,
  timezone,
  workers,
  bookings,
  shifts = [],
  onSelectBooking,
  onSelectSlot,
}: Props) {
  if (view === 'week') {
    const days = groupWeek(bookings, dateFrom, timezone);
    const { startHour, endHour } = hourBounds(
      bookings,
      timezone,
      shifts,
      days.map((day) => weekdayIndex(day.date)),
    );
    const hours = Array.from(
      { length: endHour - startHour },
      (_, index) => startHour + index,
    );
    const slots = slotStarts(startHour, endHour);
    const gridHeight = (endHour - startHour) * CALENDAR_HOUR_HEIGHT;

    return (
      <div className="overflow-x-auto rounded-lg border border-line bg-panel">
        <div
          className="grid min-w-[1114px] gap-px bg-line"
          style={{ gridTemplateColumns: '64px repeat(7, minmax(150px, 1fr))' }}
        >
          <div className="bg-panel p-2 text-xs font-semibold text-muted">Hora</div>
          {days.map((day) => (
            <h2
              key={day.date}
              className="bg-panel p-2 text-center text-sm font-semibold text-ink"
            >
              {formatDateLabel(day.date)}
            </h2>
          ))}

          <div className="relative bg-panel" style={{ height: gridHeight }}>
            {hours.map((hour, index) => (
              <span
                key={hour}
                className="absolute right-2 -translate-y-1/2 text-xs text-muted"
                style={{ top: index * CALENDAR_HOUR_HEIGHT }}
              >
                {String(hour).padStart(2, '0')}:00
              </span>
            ))}
          </div>

          {days.map((day) => (
            <div key={day.date} className="relative bg-panel" style={{ height: gridHeight }}>
              {hours.map((hour, index) => (
                <span
                  key={hour}
                  aria-hidden="true"
                  className="absolute inset-x-0 border-t border-line/70"
                  style={{ top: index * CALENDAR_HOUR_HEIGHT }}
                />
              ))}
              {onSelectSlot
                ? slots.map((start) => (
                    <button
                      key={start}
                      type="button"
                      onClick={() =>
                        onSelectSlot({ date: day.date, time: timeLabel(start) })
                      }
                      aria-label={`Crear reserva el ${formatDateLabel(day.date)} a las ${timeLabel(start)}`}
                      className="absolute inset-x-0 z-0 transition hover:bg-surface focus-visible:bg-brand-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
                      style={slotBlockStyle(start, startHour, endHour)}
                    />
                  ))
                : null}
              {day.bookings.map((booking) => (
                <button
                  type="button"
                  key={booking.id}
                  onClick={() => onSelectBooking(booking)}
                  aria-label={`Ver reserva de ${booking.customer_name} a las ${formatTime(booking.start_at, timezone)}`}
                  className="absolute inset-x-1 z-10 overflow-hidden rounded-md border-l-4 bg-surface p-1.5 text-left text-xs transition hover:bg-brand-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
                  style={{
                    ...bookingBlockStyle(booking, startHour, endHour, timezone),
                    borderLeftColor:
                      workers.length > 0
                        ? workerColor(
                            workers.find((worker) => worker.id === booking.worker) ?? workers[0],
                          )
                        : 'var(--brand-primary)',
                  }}
                >
                  <span className="block font-semibold text-ink">
                    {formatTime(booking.start_at, timezone)} {booking.customer_name}
                  </span>
                  <span className="block truncate text-muted">{booking.service_name}</span>
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  }

  const { startHour, endHour } = hourBounds(bookings, timezone, shifts, [
    weekdayIndex(anchorDate),
  ]);
  const hours = Array.from(
    { length: endHour - startHour },
    (_, index) => startHour + index,
  );
  const slots = slotStarts(startHour, endHour);
  const gridHeight = (endHour - startHour) * CALENDAR_HOUR_HEIGHT;
  const columns =
    workers.length > 0
      ? workers.map((worker) => ({
          id: worker.id,
          label: worker.display_name,
          color: workerColor(worker),
          bookings: bookingsForWorker(bookings, worker.id),
        }))
      : [
          {
            id: 'all',
            label: 'Agenda',
            color: 'var(--brand-primary)',
            bookings: [...bookings].sort((first, second) =>
              first.start_at.localeCompare(second.start_at),
            ),
          },
        ];

  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-panel">
      <div
        className="grid min-w-[640px] gap-px bg-line"
        style={{ gridTemplateColumns: `64px repeat(${columns.length}, minmax(140px, 1fr))` }}
      >
        <div className="bg-panel p-2 text-xs font-semibold text-muted">
          {formatDateLabel(anchorDate)}
        </div>
        {columns.map((column) => (
          <h2 key={column.id} className="bg-panel p-2 text-center text-sm font-semibold text-ink">
            {column.label}
          </h2>
        ))}

        <div className="relative bg-panel" style={{ height: gridHeight }}>
          {hours.map((hour, index) => (
            <span
              key={hour}
              className="absolute right-2 -translate-y-1/2 text-xs text-muted"
              style={{ top: index * CALENDAR_HOUR_HEIGHT }}
            >
              {String(hour).padStart(2, '0')}:00
            </span>
          ))}
        </div>

        {columns.map((column) => {
          return (
            <div key={column.id} className="relative bg-panel" style={{ height: gridHeight }}>
              {hours.map((hour, index) => (
                <span
                  key={hour}
                  aria-hidden="true"
                  className="absolute inset-x-0 border-t border-line/70"
                  style={{ top: index * CALENDAR_HOUR_HEIGHT }}
                />
              ))}
              {onSelectSlot
                ? slots.map((start) => (
                    <button
                      key={start}
                      type="button"
                      onClick={() =>
                        onSelectSlot({
                          date: anchorDate,
                          time: timeLabel(start),
                          workerId: column.id === 'all' ? undefined : column.id,
                        })
                      }
                      aria-label={
                        column.id === 'all'
                          ? `Crear reserva el ${formatDateLabel(anchorDate)} a las ${timeLabel(start)}`
                          : `Crear reserva el ${formatDateLabel(anchorDate)} a las ${timeLabel(start)} con ${column.label}`
                      }
                      className="absolute inset-x-0 z-0 transition hover:bg-surface focus-visible:bg-brand-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
                      style={slotBlockStyle(start, startHour, endHour)}
                    />
                  ))
                : null}
              {column.bookings.map((booking) => (
                <button
                  type="button"
                  key={booking.id}
                  onClick={() => onSelectBooking(booking)}
                  aria-label={`Ver reserva de ${booking.customer_name} a las ${formatTime(booking.start_at, timezone)}`}
                  className="absolute inset-x-1 z-10 overflow-hidden rounded-md border-l-4 bg-surface p-1.5 text-left text-xs transition hover:bg-brand-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
                  style={{
                    ...bookingBlockStyle(booking, startHour, endHour, timezone),
                    borderLeftColor: column.color,
                  }}
                >
                  <span className="block font-semibold text-ink">
                    {formatTime(booking.start_at, timezone)} {booking.customer_name}
                  </span>
                  <span className="block truncate text-muted">{booking.service_name}</span>
                </button>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

El eje mantiene un alto fijo de 64 px por hora y varias columnas; en Semana son siete días y no columnas por trabajador, por lo que el alto del bloque se calcula con el mismo porcentaje del eje. Si no hay trabajadores activos, la vista Día muestra una sola columna «Agenda» para no ocultar la grilla. Los huecos solo se renderizan si hay `onSelectSlot`, de modo que un rol de solo lectura no ve controles inactivos.

- [ ] **Step 5: Cargar los horarios y conectar el alta desde hueco**

En `web/src/api/queryKeys.ts`, agregar:

```ts
  branchWorkingHours: (companyId: UUID, branchId: UUID) =>
    ['branch-working-hours', companyId, branchId] as const,
```

En `web/src/features/agenda/AgendaPage.tsx`, agregar el cargador antes del componente:

```ts
async function fetchBranchWorkingHours(branchId: string) {
  const first = await teamApi.workingHours.list({ branch: branchId, page: 1 });
  const results = [...first.results];
  const pages = Math.ceil(first.count / 50);
  if (pages > 1) {
    const rest = await Promise.all(
      Array.from({ length: pages - 1 }, (_, index) =>
        teamApi.workingHours.list({ branch: branchId, page: index + 2 }),
      ),
    );
    rest.forEach((page) => results.push(...page.results));
  }
  return results;
}
```

Agregar el estado del hueco junto a `createOpen`:

```ts
  const [initialSlot, setInitialSlot] = useState<CalendarSlot | null>(null);
```

Importar el tipo:

```ts
import type { CalendarSlot } from './agendaLayout';
```

Agregar la consulta de horarios después de `bookingsQuery`:

```ts
  const shiftsQuery = useQuery({
    queryKey: queryKeys.branchWorkingHours(company?.id ?? '', branchId),
    queryFn: () => fetchBranchWorkingHours(branchId),
    enabled: Boolean(company && branchId),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const shifts = shiftsQuery.data ?? [];
```

Actualizar la acción del encabezado para limpiar el hueco:

```tsx
  actions={
    can('bookings.write') ? (
      <Button
        onClick={() => {
          setInitialSlot(null);
          setCreateOpen(true);
        }}
      >
        Nueva reserva
      </Button>
    ) : null
  }
```

Reemplazar el bloque que decidía entre estado vacío y calendario por:

```tsx
      <div className="mt-4">
        {workersQuery.isLoading || bookingsQuery.isLoading ? (
          <Skeleton rows={6} />
        ) : (
          <AgendaCalendar
            view={view}
            anchorDate={anchorDate}
            dateFrom={weekRange(anchorDate).date_from}
            timezone={timezone}
            workers={columns}
            bookings={bookings}
            shifts={shifts}
            onSelectBooking={setSelected}
            onSelectSlot={
              can('bookings.write')
                ? (slot) => {
                    setInitialSlot(slot);
                    setCreateOpen(true);
                  }
                : undefined
            }
          />
        )}
        {shiftsQuery.isError ? (
          <p className="mt-2 text-xs text-muted">
            No se pudieron cargar los horarios de atención; el eje usa 08:00–20:00.
          </p>
        ) : null}
      </div>
```

El calendario ya no se oculta cuando no hay reservas: una agenda vacía debe mostrar la grilla para poder crear desde un hueco. Tampoco se oculta cuando no hay trabajadores: la vista Día usa una sola columna «Agenda» y la Semana mantiene sus siete días.

Agregar `initialSlot` al diálogo:

```tsx
      <BookingCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        defaultBranchId={branchId}
        defaultDate={anchorDate}
        initialSlot={initialSlot}
        onCreated={() => {
          void queryClient.invalidateQueries({ queryKey: ['bookings', company?.id] });
          setCreateOpen(false);
        }}
      />
```

- [ ] **Step 6: Precargar el hueco en el diálogo**

En `web/src/features/agenda/BookingCreateDialog.tsx`, importar:

```ts
import { isoToDateTimeLocal } from '../../lib/dates';
import type { CalendarSlot } from './agendaLayout';
```

Agregar la propiedad a `Props` y al parámetro:

```ts
type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultBranchId: string;
  defaultDate: string;
  initialSlot?: CalendarSlot | null;
  onCreated: (booking: Booking) => void;
};
```

```tsx
export function BookingCreateDialog({
  open,
  onOpenChange,
  defaultBranchId,
  defaultDate,
  initialSlot = null,
  onCreated,
}: Props) {
```

Después de `const customerMode = watch('customerMode');`, calcular la zona de la sucursal:

```ts
  const timezone =
    branches.find((item) => item.id === branch)?.timezone ?? 'America/Santiago';
```

Reemplazar el efecto de apertura por:

```tsx
  useEffect(() => {
    if (!open) return;
    reset({
      branch: defaultBranchId,
      service: '',
      worker: initialSlot?.workerId ?? '',
      date: initialSlot?.date ?? defaultDate,
      notes: '',
      customerMode: 'existing',
      customerId: '',
      first_name: '',
      last_name: '',
      email: '',
      phone: '',
    });
    setSlot(null);
    setCustomerSearch('');
    setBanner(null);
  }, [defaultBranchId, defaultDate, initialSlot, open, reset]);
```

Después de `availabilityQuery`, agregar la preselección del cupo exacto:

```tsx
  useEffect(() => {
    if (!open || !initialSlot || !availabilityQuery.data) return;
    if (slot) return;
    if (date !== initialSlot.date) return;
    if (initialSlot.workerId && worker !== initialSlot.workerId) return;
    const wanted = `${initialSlot.date}T${initialSlot.time}`;
    const match = availabilityQuery.data.slots.find(
      (item) => isoToDateTimeLocal(item.start_at, timezone) === wanted,
    );
    setSlot(match ? match.start_at : null);
  }, [availabilityQuery.data, date, initialSlot, open, slot, timezone, worker]);
```

Dentro del `fieldset` de "Horario disponible", después del `legend`, agregar el aviso del horario solicitado:

```tsx
          {initialSlot ? (
            <p className="mb-2 text-xs text-muted">
              Horario solicitado desde la agenda: {initialSlot.date} a las {initialSlot.time}.
              Se marca automáticamente si sigue disponible para el servicio elegido.
            </p>
          ) : null}
```

Si el cupo exacto ya no existe, no se selecciona otro distinto: el usuario elige uno de los cupos ofrecidos por el servidor. El alta sigue exigiendo un cupo presionado y el `409` se conserva.

- [ ] **Step 7: Ejecutar las pruebas y verificar**

Run:

```bash
cd web
npm run test -- src/features/agenda
npm run test
npm run build
npm run lint
```

Expected: las pruebas de agenda pasan (incluye eje con horarios, franjas y precarga del hueco); la suite completa queda verde; build y lint sin errores.

- [ ] **Step 8: Validación visual**

Con datos locales, en 1280 px y 768 px, claro y oscuro:

- Semana muestra siete columnas con eje horario alineado y desplazamiento horizontal en 768 px.
- El rango comienza y termina según el horario de atención; sin horarios, usa 08:00–20:00 y muestra el aviso.
- Un hueco se enfoca con teclado, muestra un nombre accesible y abre el alta con día, hora y trabajador.
- Una reserva fuera del horario amplía el eje sin recortarse.
- Un rol sin `bookings.write` ve la grilla y las reservas, pero ningún hueco clicable.

- [ ] **Step 9: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/src/api/queryKeys.ts web/src/features/agenda
git commit -m "feat(web): add hour-axis calendar and booking creation from empty slots"
```

---

### Task 20: Infraestructura Playwright, acceso y agenda de punta a punta

**Files:**
- Create: `web/playwright.config.ts`, `web/.env.e2e.example`, `web/e2e/global-setup.ts`, `web/e2e/support/env.ts`, `web/e2e/support/api.ts`, `web/e2e/support/session.ts`, `web/e2e/support/seed.ts`, `web/e2e/auth.spec.ts`, `web/e2e/agenda.spec.ts`, `web/e2e/customers.spec.ts`, `web/e2e/inventory.spec.ts`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: la app construida en las tareas 1–19B (incluye el inventario de solo lectura y el calendario con eje horario), la API local en `127.0.0.1:8000` y el usuario con membresías demo.
- Produces:
  - `e2eEnv` con URL del panel, URL de la API, credenciales y nombres de empresa.
  - `openSession(companyName?)`, `listCompanies(token)`, `apiCall(path, options)` y `apiUpload(path, form, options)` en `e2e/support/api.ts`.
  - `readSharedSession()`, `writeSharedSession(session)` e `installSession(page, session?)` en `e2e/support/session.ts`.
  - `seedCompany(session, suffix, { withBooking })`, `dateInZone`, `weekdayIndex`, `uniqueSuffix` y `BOOKING_OFFSET_DAYS` en `e2e/support/seed.ts`.

La sesión compartida se crea una sola vez por suite y cada prueba la inyecta en `localStorage`; la llamada de refresh se responde con el access token de esa sesión para no rotar el refresh ni crear un contexto tenant por prueba (el backend limita a 20 contextos activos por usuario). El inicio de sesión real se cubre en `auth.spec.ts`.

- [ ] **Step 1: Documentar variables y artefactos de E2E**

`web/.env.e2e.example`:

```text
E2E_WEB_URL=http://127.0.0.1:5173
E2E_API_URL=http://127.0.0.1:8000
E2E_EMAIL=superadmin@agenda.app
E2E_PASSWORD=
E2E_COMPANY=Estudio Aurora
E2E_OTHER_COMPANY=Marca Demo Visual
```

Añadir a `.gitignore`:

```gitignore
web/.env.e2e
web/e2e/.auth/
```

`web/e2e/.auth/` guarda `session.json` con tokens locales; nunca se versiona.

- [ ] **Step 2: Configurar Playwright**

`web/playwright.config.ts`:

```ts
import { defineConfig, devices } from '@playwright/test';

const webBaseUrl = process.env.E2E_WEB_URL ?? 'http://127.0.0.1:5173';
const apiBaseUrl = process.env.E2E_API_URL ?? 'http://127.0.0.1:8000';

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: webBaseUrl,
    locale: 'es-CL',
    timezoneId: 'America/Santiago',
    viewport: { width: 1280, height: 900 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 900 } },
    },
  ],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5173',
    url: webBaseUrl,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: { VITE_API_BASE_URL: apiBaseUrl },
  },
});
```

Playwright levanta solo Vite. Django se inicia aparte con `python manage.py runserver`; el `globalSetup` falla con un mensaje claro si la API no responde.

`web/e2e/global-setup.ts`:

```ts
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
```

- [ ] **Step 3: Leer variables y hablar con la API desde Node**

`web/e2e/support/env.ts`:

```ts
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
```

`web/e2e/support/api.ts`:

```ts
import { e2eEnv } from './env';

export type Company = {
  id: string;
  name: string;
  display_name: string;
  slug: string;
};

export type Branch = {
  id: string;
  name: string;
  timezone: string;
  active: boolean;
};

export type TenantContext = {
  id: string;
  company: string;
  company_name: string;
  expires_at: string;
};

export type E2ESession = {
  access: string;
  refresh: string;
  companyId: string;
  contextId: string;
  companyName: string;
};

type CallOptions = {
  method?: string;
  token?: string;
  contextId?: string;
  body?: unknown;
};

export async function apiCall<T>(path: string, options: CallOptions = {}): Promise<T> {
  const headers = new Headers();
  headers.set('Accept', 'application/json');
  if (options.body !== undefined) headers.set('Content-Type', 'application/json');
  if (options.token) headers.set('Authorization', `Bearer ${options.token}`);
  if (options.contextId) headers.set('X-Tenant-Context', options.contextId);

  const method = options.method ?? 'GET';
  const response = await fetch(`${e2eEnv.apiBaseUrl}${path}`, {
    method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  if (!response.ok) {
    throw new Error(`${method} ${path} respondió ${response.status()}: ${await response.text()}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

type UploadOptions = {
  token: string;
  contextId: string;
  method?: 'POST' | 'PATCH' | 'PUT';
};

export async function apiUpload<T>(
  path: string,
  form: FormData,
  options: UploadOptions,
): Promise<T> {
  const method = options.method ?? 'POST';
  const response = await fetch(`${e2eEnv.apiBaseUrl}${path}`, {
    method,
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${options.token}`,
      'X-Tenant-Context': options.contextId,
    },
    body: form,
  });
  if (!response.ok) {
    throw new Error(`${method} ${path} respondió ${response.status()}: ${await response.text()}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function listCompanies(token: string): Promise<Company[]> {
  return apiCall<Company[]>('/api/v1/companies/mine/', { token });
}

export async function openSession(companyName?: string): Promise<E2ESession> {
  const tokens = await apiCall<{ access: string; refresh: string }>('/api/v1/auth/token/', {
    method: 'POST',
    body: { email: e2eEnv.email, password: e2eEnv.password },
  });
  const companies = await listCompanies(tokens.access);
  const company = companyName
    ? companies.find((item) => [item.name, item.display_name, item.slug].includes(companyName))
    : companies[0];

  if (!company) {
    throw new Error(
      `La cuenta E2E no tiene acceso a "${companyName ?? 'ninguna empresa'}". ` +
        `Empresas disponibles: ${companies.map((item) => item.name).join(', ') || 'ninguna'}.`,
    );
  }

  const context = await apiCall<TenantContext>('/api/v1/tenant-contexts/', {
    method: 'POST',
    token: tokens.access,
    body: { company: company.id },
  });

  return {
    access: tokens.access,
    refresh: tokens.refresh,
    companyId: company.id,
    contextId: context.id,
    companyName: company.display_name || company.name,
  };
}
```

- [ ] **Step 4: Inyectar la sesión y sembrar datos únicos**

`web/e2e/support/session.ts`:

```ts
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
```

`web/e2e/support/seed.ts`:

```ts
import type { Branch, E2ESession } from './api';
import { apiCall } from './api';

type Paginated<T> = { results: T[] };

export type Seed = {
  branch: Branch;
  service: { id: string; name: string };
  worker: { id: string; display_name: string };
  customer: { id: string; display_name: string };
  date: string;
  booking?: { id: string };
};

export const BOOKING_OFFSET_DAYS = 3;

export function uniqueSuffix(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

async function list<T>(session: E2ESession, path: string): Promise<T[]> {
  const data = await apiCall<Paginated<T> | T[]>(path, {
    token: session.access,
    contextId: session.contextId,
  });
  return Array.isArray(data) ? data : data.results;
}

export function dateInZone(timeZone: string, offsetDays: number): string {
  const formatted = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
  const [year, month, day] = formatted.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, day + offsetDays)).toISOString().slice(0, 10);
}

export function weekdayIndex(date: string): number {
  const [year, month, day] = date.split('-').map(Number);
  return (new Date(Date.UTC(year, month - 1, day)).getUTCDay() + 6) % 7;
}

export async function seedCompany(
  session: E2ESession,
  suffix: string,
  options: { withBooking?: boolean } = {},
): Promise<Seed> {
  const auth = { token: session.access, contextId: session.contextId };
  const branches = await list<Branch>(session, '/api/v1/branches/?active=true&page=1');
  const branch =
    branches[0] ??
    (await apiCall<Branch>('/api/v1/branches/', {
      ...auth,
      method: 'POST',
      body: {
        name: `Sucursal ${suffix}`,
        code: `E${suffix.slice(-6)}`.toUpperCase(),
        timezone: 'America/Santiago',
        active: true,
      },
    }));

  const service = await apiCall<Seed['service']>('/api/v1/services/', {
    ...auth,
    method: 'POST',
    body: {
      name: `Servicio ${suffix}`,
      description: 'Datos de prueba E2E',
      duration_minutes: 30,
      price: '15000.00',
      buffer_before_minutes: 0,
      buffer_after_minutes: 0,
      branches: [branch.id],
      active: true,
    },
  });

  const worker = await apiCall<Seed['worker']>('/api/v1/workers/', {
    ...auth,
    method: 'POST',
    body: {
      first_name: 'Trabajador',
      last_name: suffix,
      job_title: 'E2E',
      color: '#2563EB',
      branches: [branch.id],
      active: true,
    },
  });

  for (let weekday = 0; weekday < 7; weekday += 1) {
    await apiCall('/api/v1/working-hours/', {
      ...auth,
      method: 'POST',
      body: {
        worker: worker.id,
        branch: branch.id,
        weekday,
        start_time: '08:00:00',
        end_time: '20:00:00',
      },
    });
  }

  const customer = await apiCall<Seed['customer']>('/api/v1/customers/', {
    ...auth,
    method: 'POST',
    body: {
      first_name: 'Cliente',
      last_name: suffix,
      email: `e2e-${suffix}@example.com`,
      phone: '+56911112222',
    },
  });

  const date = dateInZone(branch.timezone, BOOKING_OFFSET_DAYS);
  let booking: Seed['booking'];

  if (options.withBooking) {
    const availability = await apiCall<{ slots: { start_at: string }[] }>(
      `/api/v1/bookings/availability/?branch=${branch.id}&service=${service.id}` +
        `&worker=${worker.id}&date=${date}`,
      auth,
    );
    const slot = availability.slots[0];
    if (!slot) throw new Error('El trabajador E2E no tiene cupos en la fecha elegida.');

    booking = await apiCall<{ id: string }>('/api/v1/bookings/', {
      ...auth,
      method: 'POST',
      body: {
        branch: branch.id,
        customer: customer.id,
        service: service.id,
        worker: worker.id,
        start_at: slot.start_at,
        notes: 'Reserva E2E',
      },
    });
  }

  return { branch, service, worker, customer, date, booking };
}
```

- [ ] **Step 5: Cubrir el acceso real con la interfaz**

`web/e2e/auth.spec.ts`:

```ts
import { expect, test, type Page } from '@playwright/test';

import { e2eEnv } from './support/env';

test.describe.configure({ mode: 'serial' });

async function signIn(page: Page) {
  await page.goto('/login');
  await page.getByLabel('Correo', { exact: true }).fill(e2eEnv.email);
  await page.getByLabel('Contraseña', { exact: true }).fill(e2eEnv.password);
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page.getByRole('heading', { name: /Elige una empresa|Agenda/ })).toBeVisible();

  if (await page.getByRole('heading', { name: 'Elige una empresa' }).isVisible()) {
    await page.getByRole('button', { name: new RegExp(e2eEnv.companyName) }).click();
  }

  await expect(page.getByRole('heading', { name: 'Agenda' })).toBeVisible();
}

test('inicia sesión y entra a la agenda de la empresa', async ({ page }) => {
  await signIn(page);
  await expect(page.getByRole('navigation', { name: 'Secciones' }).first()).toBeVisible();
});

test('rechaza credenciales inválidas', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Correo', { exact: true }).fill(e2eEnv.email);
  await page.getByLabel('Contraseña', { exact: true }).fill(`${e2eEnv.password}-incorrecta`);
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test('cierra la sesión y limpia el almacenamiento', async ({ page }) => {
  await signIn(page);
  await page.getByRole('button', { name: 'Salir' }).click();

  await expect(page.getByRole('heading', { name: 'Panel del operador' })).toBeVisible();
  const keys = await page.evaluate(() => Object.keys(localStorage));
  expect(keys).toEqual([]);
});
```

El backend limita `/auth/token/` a 5 intentos por minuto. Estas pruebas son seriales y suman 3 intentos; si se repiten con reintentos dentro del mismo minuto, espera un minuto antes de relanzar.

- [ ] **Step 6: Cubrir alta desde hueco, reprogramación y cancelación en la agenda**

`web/e2e/agenda.spec.ts`:

```ts
import { expect, test, type Page } from '@playwright/test';

import { formatDateLabel } from '../src/lib/dates';
import type { Seed } from './support/seed';
import { BOOKING_OFFSET_DAYS, seedCompany, uniqueSuffix } from './support/seed';
import { installSession, readSharedSession } from './support/session';

const session = readSharedSession();
let seed: Seed;

test.beforeAll(async () => {
  seed = await seedCompany(session, uniqueSuffix());
});

async function openSeededDay(page: Page) {
  await installSession(page, session);
  await page.goto('/agenda');
  await expect(page.getByRole('heading', { name: 'Agenda' })).toBeVisible();
  await page.getByLabel('Sucursal').selectOption({ label: seed.branch.name });
  for (let index = 0; index < BOOKING_OFFSET_DAYS; index += 1) {
    await page.getByRole('button', { name: 'Siguiente' }).click();
  }
}

test('crea, reprograma y cancela una reserva con un cupo real', async ({ page }) => {
  await openSeededDay(page);

  await page.getByRole('button', { name: 'Nueva reserva' }).click();
  const createDialog = page.getByRole('dialog');
  await createDialog.getByLabel('Sucursal').selectOption({ label: seed.branch.name });
  await createDialog.getByLabel('Día').fill(seed.date);
  await createDialog
    .getByLabel('Servicio')
    .selectOption({ label: `${seed.service.name} · 30 min` });
  await createDialog
    .getByLabel('Trabajador')
    .selectOption({ label: seed.worker.display_name });

  const slots = createDialog.getByRole('button', { name: /^\d{2}:\d{2}$/ });
  await expect(slots.first()).toBeVisible();
  await slots.first().click();

  await createDialog
    .getByLabel('Cliente', { exact: true })
    .selectOption({ label: seed.customer.display_name });
  await createDialog.getByLabel('Notas').fill('Reserva creada desde E2E');
  await createDialog.getByRole('button', { name: 'Crear reserva' }).click();

  await expect(createDialog).toBeHidden();
  const bookingBlock = page.getByRole('button', {
    name: new RegExp(seed.customer.display_name),
  });
  await expect(bookingBlock).toHaveCount(1);

  await bookingBlock.click();
  const detail = page.getByRole('dialog');
  const startBefore = await detail.locator('dd').first().textContent();

  await detail.getByRole('button', { name: 'Reprogramar' }).click();
  const rescheduleSlots = detail.getByRole('button', { name: /^\d{2}:\d{2}$/ });
  await expect(rescheduleSlots.nth(1)).toBeVisible();
  await rescheduleSlots.nth(1).click();
  await detail.getByRole('button', { name: 'Reprogramar reserva' }).click();
  await expect(detail.locator('dd').first()).not.toHaveText(startBefore ?? '');

  await detail.getByRole('button', { name: 'Cancelar reserva' }).click();
  await detail.getByLabel('Motivo de cancelación').fill('Cancelada desde E2E');
  await detail.getByRole('button', { name: 'Confirmar cancelación' }).click();
  await expect(detail.getByText('Cancelada')).toBeVisible();

  await detail.getByRole('button', { name: 'Cerrar' }).click();
  await expect(page.getByRole('button', { name: new RegExp(seed.customer.display_name) })).toBeVisible();
});

test('abre el alta desde un hueco con día, hora y cupo preseleccionados', async ({ page }) => {
  await openSeededDay(page);
  await page.getByRole('button', { name: 'Semana' }).click();
  await expect(page.getByRole('heading', { name: formatDateLabel(seed.date) })).toBeVisible();

  await page
    .getByRole('button', {
      name: `Crear reserva el ${formatDateLabel(seed.date)} a las 14:00`,
    })
    .click();

  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/Horario solicitado desde la agenda/)).toBeVisible();
  await expect(dialog.getByLabel('Día')).toHaveValue(seed.date);

  await dialog
    .getByLabel('Servicio')
    .selectOption({ label: `${seed.service.name} · 30 min` });
  await dialog
    .getByLabel('Trabajador')
    .selectOption({ label: seed.worker.display_name });

  await expect(dialog.getByRole('button', { name: /^14:00$/ })).toBeVisible();
  await dialog
    .getByLabel('Cliente', { exact: true })
    .selectOption({ label: seed.customer.display_name });
  await dialog.getByRole('button', { name: 'Crear reserva' }).click();

  await expect(dialog).toBeHidden();
  await expect(
    page.getByRole('button', {
      name: `Ver reserva de ${seed.customer.display_name} a las 14:00`,
    }),
  ).toBeVisible();
});
```

- [ ] **Step 7: Cubrir clientes, búsqueda e historial**

`web/e2e/customers.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

import type { Seed } from './support/seed';
import { seedCompany, uniqueSuffix } from './support/seed';
import { installSession, readSharedSession } from './support/session';

const session = readSharedSession();
let seed: Seed;

test.beforeAll(async () => {
  seed = await seedCompany(session, uniqueSuffix(), { withBooking: true });
});

test('busca un cliente y abre su historial de reservas', async ({ page }) => {
  await installSession(page, session);
  await page.goto('/clientes');
  await expect(page.getByRole('heading', { name: 'Clientes' })).toBeVisible();

  await page.getByLabel('Buscar').fill(seed.customer.display_name);
  const row = page.getByRole('row', { name: new RegExp(seed.customer.display_name) });
  await expect(row).toBeVisible();

  await row.getByRole('button', { name: 'Historial' }).click();
  const history = page.getByRole('dialog');
  await expect(
    history.getByRole('heading', { name: `Historial de ${seed.customer.display_name}` }),
  ).toBeVisible();
  await expect(history.getByText(seed.service.name)).toBeVisible();
  await expect(history.getByText('Agendada')).toBeVisible();
});

test('crea un cliente desde el panel y lo encuentra por búsqueda', async ({ page }) => {
  const suffix = uniqueSuffix();
  await installSession(page, session);
  await page.goto('/clientes');
  await expect(page.getByRole('heading', { name: 'Clientes' })).toBeVisible();

  await page.getByRole('button', { name: 'Nuevo cliente' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Nombre').fill('Cliente');
  await dialog.getByLabel('Apellido').fill(suffix);
  await dialog.getByLabel('Correo').fill(`e2e-cliente-${suffix}@example.com`);
  await dialog.getByLabel('Teléfono').fill('+56922223333');
  await dialog.getByRole('button', { name: 'Guardar cliente' }).click();
  await expect(dialog).toBeHidden();

  await page.getByLabel('Buscar').fill(`Cliente ${suffix}`);
  await expect(page.getByRole('row', { name: new RegExp(`Cliente ${suffix}`) })).toBeVisible();
});
```

El alta del historial usa la reserva sembrada por API; la búsqueda espera el debounce de la página sin `waitForTimeout`.

- [ ] **Step 8: Cubrir inventario de solo lectura y descarga**

`web/e2e/inventory.spec.ts`:

```ts
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
```

La empresa E2E debe tener la función `inventory` habilitada y la cuenta `inventory.read`; la cuenta demo de propietario cumple ambos. El archivo se sube por multipart con `apiUpload` porque `apiCall` serializa JSON. La descarga usa un blob autenticado, así que Playwright observa el nombre sugerido por el atributo `download`, no una URL pública.

- [ ] **Step 9: Ejecutar la suite E2E**

Preparar el entorno:

```bash
cd web
npm run e2e:install
cp .env.e2e.example .env.e2e
```

Editar `web/.env.e2e` y completar `E2E_PASSWORD` con la clave local del usuario demo.

En otra terminal, con el entorno virtual activo:

```bash
cd backend
python manage.py runserver
```

Run:

```bash
cd web
npm run e2e
```

Expected: 8 tests PASS (3 acceso, 2 agenda, 2 clientes, 1 inventario). El primer arranque crea `web/e2e/.auth/session.json` y reutiliza Vite si ya estaba en `5173`.

Si falla la preparación, abrir `playwright-report/index.html` y revisar el trace. No aumentar timeouts sin antes confirmar que la API responde en `8000`.

- [ ] **Step 10: Commit (requiere autorización explícita de Carlos)**

```bash
git add .gitignore web/playwright.config.ts web/.env.e2e.example web/e2e
git commit -m "test(web): add Playwright suite for auth, agenda, customers and inventory"
```

---

### Task 21: E2E de equipo, resumen y marca

**Files:**
- Create: `web/e2e/team.spec.ts`, `web/e2e/summary.spec.ts`, `web/e2e/branding.spec.ts`

**Interfaces:**
- Consumes: `e2e/support/*` de la tarea 20, `WEEKDAYS` de `src/lib/format.ts` y `formatMoney` para comparar totales.
- Produces: cobertura E2E del flujo servicio → trabajador → horario → cupo, de los totales de resumen contra la API y del editor de marca con restauración de datos.

- [ ] **Step 1: Cubrir el flujo de equipo hasta la disponibilidad**

`web/e2e/team.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

import { WEEKDAYS } from '../src/lib/format';
import type { Seed } from './support/seed';
import {
  BOOKING_OFFSET_DAYS,
  seedCompany,
  uniqueSuffix,
  weekdayIndex,
} from './support/seed';
import { installSession, readSharedSession } from './support/session';

const session = readSharedSession();
let seed: Seed;

test.beforeAll(async () => {
  seed = await seedCompany(session, uniqueSuffix());
});

test('crea servicio y trabajador, agrega horario y ofrece cupos', async ({ page }) => {
  const suffix = uniqueSuffix();
  const serviceName = `Servicio UI ${suffix}`;
  const workerName = `Trabajador ${suffix}`;

  await installSession(page, session);

  await page.goto('/servicios');
  await expect(page.getByRole('heading', { name: 'Servicios' })).toBeVisible();
  await page.getByRole('button', { name: 'Nuevo servicio' }).click();
  let dialog = page.getByRole('dialog');
  await dialog.getByLabel('Nombre').fill(serviceName);
  await dialog.getByLabel('Duración (minutos)').fill('45');
  await dialog.getByLabel('Precio').fill('18000');
  await dialog.getByRole('checkbox', { name: seed.branch.name }).check();
  await dialog.getByRole('button', { name: 'Guardar servicio' }).click();
  await expect(dialog).toBeHidden();

  await page.getByLabel('Buscar').fill(serviceName);
  await expect(page.getByRole('row', { name: new RegExp(serviceName) })).toBeVisible();

  await page.goto('/equipo');
  await expect(page.getByRole('heading', { name: 'Equipo' })).toBeVisible();
  await page.getByRole('button', { name: 'Nuevo trabajador' }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('Nombre').fill('Trabajador');
  await dialog.getByLabel('Apellido').fill(suffix);
  await dialog.getByLabel('Cargo').fill('E2E');
  await dialog.getByRole('checkbox', { name: seed.branch.name }).check();
  await dialog.getByRole('button', { name: 'Guardar trabajador' }).click();
  await expect(dialog).toBeHidden();

  await page.getByLabel('Buscar').fill(`Trabajador ${suffix}`);
  const workerRow = page.getByRole('row', { name: new RegExp(`Trabajador ${suffix}`) });
  await expect(workerRow).toBeVisible();
  await workerRow.getByRole('button', { name: 'Horario' }).click();

  await expect(page.getByRole('button', { name: 'Agregar horario' })).toBeVisible();
  await page.getByRole('button', { name: 'Agregar horario' }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('Sucursal').selectOption({ label: seed.branch.name });
  await dialog.getByLabel('Día').selectOption({ label: WEEKDAYS[weekdayIndex(seed.date)] });
  await dialog.getByLabel('Inicio').fill('08:00');
  await dialog.getByLabel('Término').fill('20:00');
  await dialog.getByRole('button', { name: 'Guardar horario' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText('08:00').first()).toBeVisible();

  await page.goto('/agenda');
  await expect(page.getByRole('heading', { name: 'Agenda' })).toBeVisible();
  await page.getByLabel('Sucursal').selectOption({ label: seed.branch.name });
  for (let index = 0; index < BOOKING_OFFSET_DAYS; index += 1) {
    await page.getByRole('button', { name: 'Siguiente' }).click();
  }

  await page.getByRole('button', { name: 'Nueva reserva' }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('Sucursal').selectOption({ label: seed.branch.name });
  await dialog.getByLabel('Día').fill(seed.date);
  await dialog.getByLabel('Servicio').selectOption({ label: `${serviceName} · 45 min` });
  await dialog.getByLabel('Trabajador').selectOption({ label: workerName });

  await expect(dialog.getByRole('button', { name: /^\d{2}:\d{2}$/ }).first()).toBeVisible();
});
```

El trabajador recibe horario solo el día de `seed.date`; por eso la prueba abre la agenda en esa fecha antes de pedir disponibilidad. Si la empresa demo no tiene sucursales, `seedCompany` crea una.

- [ ] **Step 2: Comparar el resumen con la API**

`web/e2e/summary.spec.ts`:

```ts
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
```

La prueba lee las fechas que la página calculó y consulta la API con esos mismos valores; funciona con datos vacíos y con ventas reales de la demo.

- [ ] **Step 3: Editar la marca y restaurar los valores originales**

`web/e2e/branding.spec.ts`:

```ts
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
```

`afterAll` restaura nombre, identificador, colores y tema aunque la prueba falle; la demo vuelve a su estado anterior.

- [ ] **Step 4: Ejecutar la suite E2E**

Run:

```bash
cd web
npm run e2e
```

Expected: 11 tests PASS (3 acceso, 2 agenda, 2 clientes, 1 inventario, 1 equipo, 1 resumen, 1 marca). Revisar que la empresa demo conserva su nombre y colores al terminar.

- [ ] **Step 5: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/e2e/team.spec.ts web/e2e/summary.spec.ts web/e2e/branding.spec.ts
git commit -m "test(web): cover team, summary and branding flows"
```

---

### Task 22: E2E de aislamiento, sesión, accesibilidad y 768 px

**Files:**
- Create: `web/e2e/isolation.spec.ts`, `web/e2e/session.spec.ts`, `web/e2e/a11y.spec.ts`, `web/e2e/responsive.spec.ts`

**Interfaces:**
- Consumes: `e2e/support/*`, `@axe-core/playwright` y al menos dos empresas en la cuenta E2E para el caso de aislamiento.
- Produces: evidencia automática de que cambiar de empresa usa otro `X-Tenant-Context` y no muestra datos previos, de que no se persisten datos de negocio, de WCAG AA en claro/oscuro y de ausencia de desbordes a 768 px.

- [ ] **Step 1: Probar el aislamiento al cambiar de empresa**

`web/e2e/isolation.spec.ts`:

```ts
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
  await page.goto('/clientes');
  await page.getByLabel('Buscar').fill(seed.customer.display_name);
  await expect(page.getByText('No hay clientes que coincidan con los filtros.')).toBeVisible();

  await expect.poll(() => customerHeaders.length).toBeGreaterThan(0);
  expect(customerHeaders.every((contextId) => contextId !== session.contextId)).toBe(true);
});
```

Si la cuenta E2E tiene una sola empresa, la prueba se marca como omitida; la suite sigue verde. El cambio de empresa navega a `/agenda` aunque la segunda empresa no tenga sucursales (en ese caso la agenda muestra el estado vacío).

- [ ] **Step 2: Comprobar restauración de sesión y almacenamiento mínimo**

`web/e2e/session.spec.ts`:

```ts
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
```

La recarga vuelve a ejecutar el `addInitScript` con la misma sesión compartida y el refresh interceptado, así que no consume el token real ni crea otro contexto.

- [ ] **Step 3: Auditar accesibilidad en claro y oscuro**

`web/e2e/a11y.spec.ts`:

```ts
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
```

Si axe reporta violaciones, corregir la pantalla en la tarea correspondiente (contraste, nombre accesible o jerarquía de encabezados) y volver a ejecutar; no se agregan exclusiones.

- [ ] **Step 4: Verificar el diseño a 768 px**

`web/e2e/responsive.spec.ts`:

```ts
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
```

Las tablas y el calendario deben desplazarse dentro de su contenedor, no en el documento.

- [ ] **Step 5: Ejecutar la suite completa**

Run:

```bash
cd web
npm run e2e
```

Expected: 16 tests PASS (11 previos + aislamiento, sesión, accesibilidad de páginas, accesibilidad del diálogo y 768 px). Si la cuenta no tiene una segunda empresa, el total baja a 15 con una prueba omitida.

- [ ] **Step 6: Commit (requiere autorización explícita de Carlos)**

```bash
git add web/e2e/isolation.spec.ts web/e2e/session.spec.ts web/e2e/a11y.spec.ts web/e2e/responsive.spec.ts
git commit -m "test(web): verify tenant isolation, session and accessibility"
```

---

### Task 23: Build de producción, despliegue y documentación

**Files:**
- Create: `web/.env.production.example`, `web/deploy/nginx.conf.example`, `docs/web-admin.md`
- Modify: `.gitignore`, `README.md`

**Interfaces:**
- Consumes: todas las rutas, variables y scripts definidos en las tareas anteriores (`npm run lint`, `npm run test`, `npm run build`, `npm run e2e`, `VITE_API_BASE_URL`, `E2E_*`).
- Produces: build estático en `web/dist/` listo para servirse detrás de Nginx con `/api`, `/b` y `/media` en el mismo origen; documentación operativa en `docs/web-admin.md` enlazada desde el README.

- [ ] **Step 1: Definir el entorno de producción**

`web/.env.production.example`:

```text
# Vacío = mismo origen. Nginx sirve el SPA y hace proxy de /api, /b y /media.
VITE_API_BASE_URL=
```

Agregar a `.gitignore`:

```gitignore
web/.env.production
```

Vite carga `.env.production` automáticamente con `npm run build`. El valor vacío es intencional: `import.meta.env.VITE_API_BASE_URL` queda como cadena vacía y el cliente construye URLs relativas al origen del panel. Si el panel y la API quedan en dominios distintos, define la URL absoluta y agrega ese origen a `DJANGO_CORS_ORIGINS`.

- [ ] **Step 2: Crear el ejemplo de Nginx**

`web/deploy/nginx.conf.example`:

```nginx
# Panel web del operador AGENDA.
# Reemplaza /srv/agenda por la ruta real del repositorio y panel.example.com
# por el dominio definitivo.
server {
    listen 80;
    server_name panel.example.com;

    # Con HTTPS, redirige HTTP y define el bloque TLS:
    # return 301 https://$host$request_uri;

    server_tokens off;

    root /srv/agenda/web/dist;
    index index.html;

    # Los logos aceptan hasta 2 MB más el envoltorio multipart.
    client_max_body_size 3m;

    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy no-referrer always;
    add_header X-Frame-Options DENY always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'" always;
    # HSTS solo con HTTPS estable:
    # add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;

    location /assets/ {
        try_files $uri =404;
        expires 1y;
    }

    location = /index.html {
        expires -1;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Página pública de reservas servida por Django.
    location /b/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Logos de las empresas: MEDIA_ROOT del backend (backend/media/).
    location /media/ {
        alias /srv/agenda/backend/media/;
        try_files $uri =404;
        expires 7d;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

`style-src` incluye `'unsafe-inline'` porque React aplica las variables de la marca como estilos en línea; `script-src` sigue limitado a `'self'`. Las cabeceras de seguridad se heredan en todas las ubicaciones porque ninguna define `add_header` propio; `expires` no rompe esa herencia.

- [ ] **Step 3: Documentar el panel**

`docs/web-admin.md`:

````markdown
# Panel web del operador

SPA en `web/` para operar una empresa de AGENDA: agenda, clientes, servicios,
equipo, inventario (solo lectura), resumen y marca. Consume la misma API que la
app móvil; no hay endpoints exclusivos del panel.

## Requisitos

- Node.js 24 y npm.
- Backend en `http://127.0.0.1:8000` con migraciones aplicadas.
- Una empresa con al menos una sucursal y una cuenta con membresía en ella
  (propietario, administrador o trabajador).

## Desarrollo local

Terminal 1:

```bash
cd backend
python manage.py runserver
```

Terminal 2:

```bash
cd web
cp .env.example .env
npm install
npm run dev
```

Abre `http://127.0.0.1:5173`. Vite hace proxy de `/api` y `/media` hacia
Django; ese proxy solo existe en desarrollo. En Windows usa
`Copy-Item .env.example .env` en PowerShell.

## Variables de entorno

| Archivo | Variable | Uso |
| --- | --- | --- |
| `web/.env` | `VITE_API_BASE_URL` | API del panel. Vacío usa el mismo origen; en desarrollo el proxy de Vite reenvía `/api`. |
| `web/.env.e2e` | `E2E_WEB_URL`, `E2E_API_URL`, `E2E_EMAIL`, `E2E_PASSWORD`, `E2E_COMPANY`, `E2E_OTHER_COMPANY` | Pruebas Playwright. Copia `web/.env.e2e.example`. |
| `web/.env.production` | `VITE_API_BASE_URL` | Build de producción. Déjalo vacío para mismo origen detrás de Nginx. |

`.env`, `.env.e2e`, `.env.production` y `web/e2e/.auth/` no se versionan.

## Scripts

| Comando | Efecto |
| --- | --- |
| `npm run dev` | Vite en `5173` con proxy a Django. |
| `npm run lint` | ESLint sobre TypeScript, hooks y accesibilidad. |
| `npm run test` | Vitest + React Testing Library + MSW. |
| `npm run build` | Chequeo de tipos y build en `dist/`. |
| `npm run preview` | Sirve `dist/` sin proxy; solo para revisar el bundle. |
| `npm run e2e` | Playwright contra Django y Vite. |
| `npm run e2e:install` | Instala Chromium para Playwright. |

## Sesión y aislamiento

- El access token vive en memoria; el refresh token y
  `{companyId, contextId, companyName}` se guardan en `localStorage`. No se
  persisten datos de negocio.
- Cambiar de empresa crea un contexto tenant nuevo y limpia la caché de
  TanStack Query. Cada consulta envía `X-Tenant-Context` y cada clave de caché
  incluye la empresa.
- Un usuario puede tener hasta 20 contextos tenant activos (8 horas cada uno).
  Si el servidor rechaza uno nuevo, cierra sesiones antiguas desde las otras
  pestañas o equipos.

## Pruebas de punta a punta

```bash
cd web
cp .env.e2e.example .env.e2e
# completa E2E_PASSWORD con la clave de la cuenta de pruebas
npm run e2e:install
npm run e2e
```

Playwright levanta Vite; Django debe estar en ejecución. `globalSetup` hace un
login real y crea una sola sesión compartida; las pruebas inyectan esa sesión y
simulan la renovación para no agotar el límite de contextos. Si
`E2E_OTHER_COMPANY` no existe, la prueba de aislamiento se omite. La suite crea
clientes, servicios, horarios y reservas reales: no la ejecutes contra
producción.

## Build y despliegue

```bash
cd web
cp .env.production.example .env.production
npm ci
npm run build
```

El resultado queda en `web/dist/`. Para servir panel y API en el mismo origen,
usa `web/deploy/nginx.conf.example` como base: sirve `dist/` con fallback a
`index.html`, hace proxy de `/api/`, `/b/` y `/media/`, y aplica CSP, HSTS
opcional y caché de assets.

Antes de publicar:

- Ajusta `root`, `alias` y `server_name` a las rutas y al dominio reales.
- Agrega el dominio a `DJANGO_ALLOWED_HOSTS` y usa `DJANGO_DEBUG=false`.
- Define `DJANGO_CORS_ORIGINS` solo si panel y API quedan en orígenes distintos;
  con el proxy de Nginx no hace falta CORS. En ese caso agrega también la URL
  absoluta de la API a `connect-src` en el CSP.
- Asegura que Nginx pueda leer `backend/media/` (logos) y que el proceso de
  Django escriba ahí.
- El admin de Django (`/admin/`) necesita `STATIC_ROOT` y `collectstatic`, que
  todavía no están configurados; queda fuera de este panel.
- Si Nginx termina TLS y Django debe construir URLs absolutas, configura
  `SECURE_PROXY_SSL_HEADER`. HSTS solo con HTTPS estable.
- Postgres, servidor de aplicaciones, correo y push pertenecen al plan general
  de despliegue.

## Seguridad asumida en v1

El refresh token en `localStorage` se acepta para v1 con CSP estricta y sin
scripts de terceros. Antes de exponer el panel a internet se migrará a cookie
httpOnly con CSRF. El CSP de ejemplo permite estilos en línea porque React
aplica las variables de la marca; los scripts solo se cargan del mismo origen.

## Validación manual

- Claro y oscuro en agenda, clientes, servicios, equipo, inventario, resumen y
  marca, a 1280 px y 768 px, sin desbordes horizontales del documento.
- Navegación completa por teclado, foco visible y diálogos con foco atrapado.
- Login, cambio de empresa y recarga: se restaura la sesión y no aparecen datos
  de la empresa anterior.
- Una cuenta sin `company.manage` no puede editar la marca; sin escritura en un
  módulo no ve sus acciones de alta o edición.

## Problemas frecuentes

- **401**: el access token expiró y el refresh falló; vuelve a iniciar sesión.
  El login acepta 5 intentos por minuto e IP.
- **403**: falta permiso, contexto tenant o la cuenta no pertenece a la empresa.
- **402**: límite del plan alcanzado (por ejemplo, trabajadores o sucursales).
- **Sin conexión**: la API no responde o `VITE_API_BASE_URL` apunta a otro
  origen sin CORS.
- **Sin sucursales o servicios**: completa la configuración de la empresa antes
  de usar la agenda.
````

- [ ] **Step 4: Enlazar la documentación desde el README**

En `README.md`, después de la sección de la app móvil y antes de `## API inicial`, agregar:

````markdown
### Panel web del operador (React)

El panel de `web/` ofrece agenda, clientes, servicios, equipo, inventario de solo
lectura, resumen y marca para operadores de una empresa. Requiere el backend en
ejecución:

```powershell
cd web
Copy-Item .env.example .env
npm install
npm run dev
```

Abre `http://127.0.0.1:5173`. Consulta `docs/web-admin.md` para variables de
entorno, pruebas E2E y despliegue con Nginx.
````

- [ ] **Step 5: Verificar lint, pruebas y build**

Run:

```bash
cd web
npm run lint
npm run test
npm run build
```

Expected: lint sin errores ni advertencias; todas las pruebas unitarias PASS; `tsc --noEmit` sin errores (incluye `e2e/` y `playwright.config.ts`); `dist/index.html` y `dist/assets/` generados, con nombres hasheados referenciados desde el HTML.

- [ ] **Step 6: Repetir la suite E2E completa**

Con Django en ejecución y `web/.env.e2e` completo:

```bash
cd web
npm run e2e
```

Expected: 16 tests PASS (15 si se omite aislamiento por falta de segunda empresa). Si algún spec falla por datos del entorno, corrige la configuración y vuelve a ejecutar; no lo marques como omitido sin justificarlo.

- [ ] **Step 7: Validación visual final en claro y oscuro**

Con el backend y `npm run dev` en ejecución, recorre `/agenda`, `/clientes`, `/servicios`, `/equipo`, `/inventario`, `/resumen` y `/marca` en las dos vistas:

1. A 1280 × 900: sidebar visible, sin scroll horizontal del documento, tablas y calendario desplazándose dentro de su contenedor.
2. A 768 × 1024: navegación superior visible, formularios y diálogos utilizables, sin desborde horizontal del documento; el calendario semanal se desplaza dentro de su contenedor.
3. Alterna `Tema claro` / `Tema oscuro` en cada pantalla y confirma contraste AA, foco visible y colores de marca legibles.
4. Abre un diálogo (alta de reserva o cliente) en ambos temas, recorre con Tab y ciérralo con Escape; el foco vuelve al disparador.
5. Cambia de empresa y confirma que no queda ningún dato de la anterior; recarga y confirma que la sesión se restaura.
6. En inventario, confirma que objetos y archivos se consultan y descargan, y que no existe ninguna acción de alta, edición o borrado.

Expected: los seis puntos se cumplen sin errores en la consola del navegador.

- [ ] **Step 8: Commit (requiere autorización explícita de Carlos)**

```bash
git add .gitignore README.md docs/web-admin.md web/.env.production.example web/deploy/nginx.conf.example
git commit -m "docs(web): document operator panel deployment and workflows"
```

---
