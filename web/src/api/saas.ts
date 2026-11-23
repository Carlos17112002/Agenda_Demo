import type { ApiClient } from './client';
import type {
  Paginated,
  SaasCompany,
  SaasCompanyCreateInput,
  SaasCompanyCreateResult,
  SaasPlan,
  SaasPlanInput,
} from './types';

export function createSaasApi(client: ApiClient) {
  return {
    companies: () => client.get<Paginated<SaasCompany>>('/api/v1/saas/companies/', { page_size: 50 }),
    plans: () => client.get<Paginated<SaasPlan>>('/api/v1/saas/plans/', { page_size: 100 }),
    createCompany: (input: SaasCompanyCreateInput) =>
      client.post<SaasCompanyCreateResult>('/api/v1/saas/companies/', input),
    createPlan: (input: SaasPlanInput) =>
      client.post<SaasPlan>('/api/v1/saas/plans/', input),
    updatePlan: (id: string, input: SaasPlanInput) =>
      client.patch<SaasPlan>(`/api/v1/saas/plans/${id}/`, input),
  };
}
