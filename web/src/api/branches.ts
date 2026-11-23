import type { ApiClient } from './client';
import type { Branch, Paginated, UUID } from './types';

export type BranchInput = {
  name: string;
  code: string;
  address: string;
  timezone: string;
};

export type BranchUpdateInput = Partial<BranchInput> & { active?: boolean };

export function createBranchesApi(client: ApiClient) {
  return {
    list: () => client.get<Paginated<Branch>>('/api/v1/branches/', { page_size: 100 }),
    create: (input: BranchInput) => client.post<Branch>('/api/v1/branches/', input),
    update: (id: UUID, input: BranchUpdateInput) =>
      client.patch<Branch>(`/api/v1/branches/${id}/`, input),
    remove: (id: UUID) => client.delete<void>(`/api/v1/branches/${id}/`),
  };
}
