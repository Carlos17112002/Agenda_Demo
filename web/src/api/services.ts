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
