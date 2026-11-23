import { vi } from 'vitest';

import type { AuthContextValue, AuthGateway } from '../auth/AuthProvider';
import type { SessionStore } from '../auth/sessionStore';
import type { Bootstrap, CompanySummary, User } from '../api/types';
import { allows } from '../lib/permissions';

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
    membership: {
      id: 'membership-1',
      role: 'owner',
      role_display: 'Propietario',
      default_branch: null,
    },
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
    permission_catalog: [
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
    role_defaults: {
      owner: ['bookings.read', 'bookings.write', 'company.manage'],
      reception: ['bookings.read', 'bookings.write', 'customers.read'],
    },
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
    me: vi.fn(overrides.me ?? (async () => makeUser())),
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
    changePassword: vi.fn(
      overrides.changePassword ??
        (async () => ({ access: 'access-c', refresh: 'refresh-c', must_change_password: false })),
    ),
  };
}

export function makeAuthValue(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  const bootstrap = overrides.bootstrap ?? makeBootstrap();
  return {
    status: 'ready',
    isSaasAdmin: false,
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
    changePassword: vi.fn(async () => {}),
    can: (required) => allows(bootstrap.permissions, required),
    hasFeature: (code) => bootstrap.features[code] ?? false,
    ...overrides,
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
