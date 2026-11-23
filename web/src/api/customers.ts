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
