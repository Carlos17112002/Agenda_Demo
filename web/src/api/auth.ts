import type { AuthGateway } from '../auth/AuthProvider';
import type { ApiClient } from './client';
import type {
  Bootstrap,
  CompanySummary,
  LoginResponse,
  PasswordChangeResponse,
  RefreshResponse,
  TenantContextResponse,
  User,
} from './types';

export function createAuthGateway(client: ApiClient): AuthGateway {
  return {
    login: (email, password) =>
      client.post<LoginResponse>('/api/v1/auth/token/', { email, password }),
    refresh: (refresh) =>
      client.post<RefreshResponse>('/api/v1/auth/token/refresh/', { refresh }),
    companies: () => client.get<CompanySummary[]>('/api/v1/companies/mine/?include=all'),
    createContext: (companyId) =>
      client.post<TenantContextResponse>('/api/v1/tenant-contexts/', { company: companyId }),
    bootstrap: () => client.get<Bootstrap>('/api/v1/mobile/bootstrap/'),
    logout: (refresh) => client.post<void>('/api/v1/auth/logout/', { refresh }),
    me: () => client.get<User>('/api/v1/auth/me/'),
    changePassword: (current, next) =>
      client.post<PasswordChangeResponse>('/api/v1/auth/password/change/', {
        current_password: current,
        new_password: next,
      }),
  };
}
