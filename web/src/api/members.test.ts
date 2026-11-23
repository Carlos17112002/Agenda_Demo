import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import { server } from '../test/server';
import { ApiClient } from './client';
import { createMembersApi } from './members';

const memberFixture = {
  id: 'membership-2',
  user_id: 'user-2',
  email: 'nueva@example.com',
  first_name: 'Nueva',
  last_name: 'Persona',
  role: 'reception',
  role_display: 'Recepción',
  default_branch: { id: 'branch-1', name: 'Providencia' },
  active: true,
  created_at: '2026-11-19T12:00:00Z',
};

function makeApi() {
  return createMembersApi(
    new ApiClient({
      baseUrl: 'http://api.test',
      getAccessToken: () => 'access-1',
      getTenantContextId: () => 'ctx-1',
    }),
  );
}

describe('membersApi', () => {
  test('crea el usuario con local y devuelve la clave temporal', async () => {
    let body: unknown = null;
    server.use(
      http.post('http://api.test/api/v1/members/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          { member: memberFixture, temporary_password: 'Temp-Phrase-123!', worker_profile: null },
          { status: 201 },
        );
      }),
    );

    const result = await makeApi().create({
      email: 'nueva@example.com',
      first_name: 'Nueva',
      role: 'reception',
      default_branch: 'branch-1',
    });

    expect(body).toMatchObject({
      email: 'nueva@example.com',
      role: 'reception',
      default_branch: 'branch-1',
    });
    expect(result.temporary_password).toBe('Temp-Phrase-123!');
  });

  test('filtra los permisos por membresía', async () => {
    let url = '';
    server.use(
      http.get('http://api.test/api/v1/permission-grants/', ({ request }) => {
        url = request.url;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );

    await makeApi().grants.list({ membership: 'membership-2' });

    expect(url).toContain('membership=membership-2');
  });
});
