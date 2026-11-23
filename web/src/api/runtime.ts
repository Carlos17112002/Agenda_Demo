import { localSessionStore } from '../auth/sessionStore';
import { createAgendaApi } from './agenda';
import { createAuthGateway } from './auth';
import { createBranchesApi } from './branches';
import { createBrandingApi } from './branding';
import { ApiClient, ApiError } from './client';
import { createCustomersApi } from './customers';
import { createInventoryApi } from './inventory';
import { createMembersApi } from './members';
import { createPublicAccountsApi } from './publicAccounts';
import { createSaasApi } from './saas';
import { createServicesApi } from './services';
import { createSummaryApi } from './summary';
import { createTeamApi } from './team';

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

export const agendaApi = createAgendaApi(apiClient);
export const customersApi = createCustomersApi(apiClient);
export const servicesApi = createServicesApi(apiClient);
export const teamApi = createTeamApi(apiClient);
export const summaryApi = createSummaryApi(apiClient);
export const brandingApi = createBrandingApi(apiClient);
export const branchesApi = createBranchesApi(apiClient);
export const inventoryApi = createInventoryApi(apiClient);
export const membersApi = createMembersApi(apiClient);
export const saasApi = createSaasApi(apiClient);
export const publicAccountsApi = createPublicAccountsApi(apiClient);
