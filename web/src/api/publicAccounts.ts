import type { ApiClient } from './client';
import type {
  Paginated, PublicPlan, RegisterCompanyInput, RegisterCompanyResponse,
  VerifyEmailResponse,
} from './types';

export function createPublicAccountsApi(client: ApiClient) {
  return {
    plans: () => client.request<Paginated<PublicPlan>>('/api/v1/plans/', { auth: false }),
    registerCompany: (input: RegisterCompanyInput) =>
      client.request<RegisterCompanyResponse>('/api/v1/auth/register-company/', {
        method: 'POST', body: input, auth: false,
      }),
    verifyEmail: (token: string) =>
      client.request<VerifyEmailResponse>('/api/v1/auth/verify-email/', {
        method: 'POST', body: { token }, auth: false,
      }),
    resendVerification: (email: string) =>
      client.request<{ detail: string }>('/api/v1/auth/resend-verification/', {
        method: 'POST', body: { email }, auth: false,
      }),
  };
}
