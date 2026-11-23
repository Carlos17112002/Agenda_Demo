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

  test('invoca fetch con el global como receptor', async () => {
    const receivers: unknown[] = [];
    vi.stubGlobal(
      'fetch',
      async function (this: unknown) {
        receivers.push(this);
        return {
          status: 200,
          ok: true,
          json: async () => ({ ok: true }),
        } as Response;
      },
    );
    try {
      await expect(makeClient().get('/api/v1/customers/')).resolves.toEqual({ ok: true });
    } finally {
      vi.unstubAllGlobals();
    }

    expect(receivers).toEqual([globalThis]);
  });

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
});
