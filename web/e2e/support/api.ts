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
    throw new Error(`${method} ${path} respondió ${response.status}: ${await response.text()}`);
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
    throw new Error(`${method} ${path} respondió ${response.status}: ${await response.text()}`);
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
