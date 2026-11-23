import type { ApiClient } from './client';
import type { ISODate, ISODateTime, Paginated, UUID } from './types';

export type BookingStatus = 'scheduled' | 'confirmed' | 'completed' | 'canceled' | 'no_show';

export type Booking = {
  id: UUID;
  company: UUID;
  branch: UUID;
  branch_name: string;
  customer: UUID;
  customer_name: string;
  customer_email: string;
  service: UUID;
  service_name: string;
  worker: UUID;
  worker_name: string;
  start_at: ISODateTime;
  end_at: ISODateTime;
  duration_minutes: number;
  price: string;
  status: BookingStatus;
  status_display: string;
  source: string;
  source_display: string;
  notes: string;
  public_code: string;
  canceled_at: ISODateTime | null;
  canceled_reason: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type BookingListParams = {
  branch?: UUID;
  worker?: UUID;
  service?: UUID;
  customer?: UUID;
  status?: BookingStatus;
  date?: ISODate;
  date_from?: ISODate;
  date_to?: ISODate;
  page?: number;
  ordering?: string;
};

export type BookingCreateInput = {
  branch: UUID;
  customer: UUID;
  service: UUID;
  worker: UUID;
  start_at: ISODateTime;
  notes?: string;
};

export type AvailabilityParams = {
  branch: UUID;
  service: UUID;
  worker: UUID;
  date: ISODate;
};

export type AvailabilitySlot = {
  start_at: ISODateTime;
  end_at: ISODateTime;
  label: string;
};

export type Availability = {
  date: ISODate;
  timezone: string;
  slots: AvailabilitySlot[];
};

export type RescheduleInput = {
  start_at: ISODateTime;
  worker?: UUID;
  reason?: string;
};

export type BookingAction = 'confirm' | 'cancel' | 'complete' | 'no-show';

export function createAgendaApi(client: ApiClient) {
  return {
    listBookings: (params: BookingListParams = {}) =>
      client.get<Paginated<Booking>>('/api/v1/bookings/', { ...params }),

    availability: (params: AvailabilityParams) =>
      client.get<Availability>('/api/v1/bookings/availability/', { ...params }),

    createBooking: (input: BookingCreateInput) =>
      client.post<Booking>('/api/v1/bookings/', input),

    rescheduleBooking: (id: UUID, input: RescheduleInput) =>
      client.post<Booking>(`/api/v1/bookings/${id}/reschedule/`, input),

    transitionBooking: (id: UUID, action: BookingAction, reason = '') =>
      client.post<Booking>(`/api/v1/bookings/${id}/${action}/`, reason ? { reason } : {}),

    updateNotes: (id: UUID, notes: string) =>
      client.patch<Booking>(`/api/v1/bookings/${id}/`, { notes }),
  };
}

export type AgendaApi = ReturnType<typeof createAgendaApi>;
