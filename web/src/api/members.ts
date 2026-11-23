import type { ApiClient } from './client';
import type { Paginated, UUID } from './types';

export type MemberRole =
  | 'owner'
  | 'admin'
  | 'manager'
  | 'reception'
  | 'worker'
  | 'inventory'
  | 'accounting';

export type Member = {
  id: UUID;
  user_id: UUID;
  email: string;
  first_name: string;
  last_name: string;
  role: MemberRole;
  role_display: string;
  default_branch: { id: UUID; name: string } | null;
  active: boolean;
  created_at: string;
};

export type MemberInput = {
  email: string;
  first_name?: string;
  last_name?: string;
  role: MemberRole;
  default_branch?: UUID | null;
  create_worker_profile?: boolean;
};

export type MemberUpdateInput = {
  first_name?: string;
  last_name?: string;
  role?: MemberRole;
  default_branch?: UUID | null;
  active?: boolean;
};

export type MemberCreateResult = {
  member: Member;
  temporary_password: string;
  worker_profile: { id: UUID } | null;
};

export type PermissionGrant = {
  id: UUID;
  membership: UUID;
  permission: string;
  effect: 'allow' | 'deny';
  branch: UUID | null;
  created_at: string;
};

export type PermissionGrantInput = {
  membership: UUID;
  permission: string;
  effect: 'allow' | 'deny';
  branch?: UUID | null;
};

export function createMembersApi(client: ApiClient) {
  return {
    list: (params: { search?: string; page?: number } = {}) =>
      client.get<Paginated<Member>>('/api/v1/members/', { ...params }),
    create: (input: MemberInput) => client.post<MemberCreateResult>('/api/v1/members/', input),
    update: (id: UUID, input: MemberUpdateInput) =>
      client.patch<Member>(`/api/v1/members/${id}/`, input),
    remove: (id: UUID) => client.delete<void>(`/api/v1/members/${id}/`),
    grants: {
      list: (params: { membership: UUID; page?: number }) =>
        client.get<Paginated<PermissionGrant>>('/api/v1/permission-grants/', { ...params }),
      create: (input: PermissionGrantInput) =>
        client.post<PermissionGrant>('/api/v1/permission-grants/', input),
      remove: (id: UUID) => client.delete<void>(`/api/v1/permission-grants/${id}/`),
    },
  };
}

export type MembersApi = ReturnType<typeof createMembersApi>;
