import type { ApiClient } from './client';
import type { ISODateTime, Paginated, UUID } from './types';

export type Weekday = 0 | 1 | 2 | 3 | 4 | 5 | 6;

export type Worker = {
  id: UUID;
  company: UUID;
  membership: UUID | null;
  first_name: string;
  last_name: string;
  display_name: string;
  email: string;
  phone: string;
  job_title: string;
  color: string;
  branches: UUID[];
  active: boolean;
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type WorkerInput = {
  first_name: string;
  last_name?: string;
  email?: string;
  phone?: string;
  job_title?: string;
  color?: string;
  branches?: UUID[];
  active?: boolean;
  membership?: UUID | null;
};

export type WorkingHours = {
  id: UUID;
  worker: UUID;
  branch: UUID;
  weekday: Weekday;
  start_time: string;
  end_time: string;
};

export type WorkingHoursInput = Omit<WorkingHours, 'id'>;

export type Break = WorkingHours & { label: string };
export type BreakInput = Omit<Break, 'id'>;

export type TimeOff = {
  id: UUID;
  worker: UUID;
  branch: UUID | null;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  reason: string;
};

export type TimeOffInput = Omit<TimeOff, 'id'>;

export type BlockedSlot = {
  id: UUID;
  worker: UUID;
  branch: UUID | null;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  reason: string;
};

export type BlockedSlotInput = Omit<BlockedSlot, 'id'>;

type ListParams = { worker?: UUID; branch?: UUID; page?: number };

type CrudApi<T, TInput> = {
  list(params?: ListParams): Promise<Paginated<T>>;
  create(input: TInput): Promise<T>;
  update(id: UUID, input: Partial<TInput>): Promise<T>;
  remove(id: UUID): Promise<void>;
};

function crud<T, TInput>(client: ApiClient, path: string): CrudApi<T, TInput> {
  return {
    list: (params = {}) => client.get<Paginated<T>>(path, { ...params }),
    create: (input) => client.post<T>(path, input),
    update: (id, input) => client.patch<T>(`${path}${id}/`, input),
    remove: (id) => client.delete<void>(`${path}${id}/`),
  };
}

export function createTeamApi(client: ApiClient) {
  return {
    workers: {
      list: (params: { search?: string; branch?: UUID; active?: boolean; page?: number } = {}) =>
        client.get<Paginated<Worker>>('/api/v1/workers/', { ...params }),
      create: (input: WorkerInput) => client.post<Worker>('/api/v1/workers/', input),
      update: (id: UUID, input: Partial<WorkerInput>) =>
        client.patch<Worker>(`/api/v1/workers/${id}/`, input),
    },
    workingHours: crud<WorkingHours, WorkingHoursInput>(client, '/api/v1/working-hours/'),
    breaks: crud<Break, BreakInput>(client, '/api/v1/breaks/'),
    timeOff: crud<TimeOff, TimeOffInput>(client, '/api/v1/time-off/'),
    blockedSlots: crud<BlockedSlot, BlockedSlotInput>(client, '/api/v1/blocked-slots/'),
  };
}

export type TeamApi = ReturnType<typeof createTeamApi>;
