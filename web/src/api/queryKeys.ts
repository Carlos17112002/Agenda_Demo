import type { BookingListParams, AvailabilityParams } from './agenda';
import type { CustomerListParams } from './customers';
import type { AssetListParams, DocumentListParams } from './inventory';
import type { ServiceListParams } from './services';
import type { SummaryParams } from './summary';
import type { UUID } from './types';

const list = (name: string, companyId: UUID, params: object) => [name, companyId, params] as const;

export const queryKeys = {
  bookings: (companyId: UUID, params: BookingListParams) => list('bookings', companyId, params),
  availability: (companyId: UUID, params: AvailabilityParams) =>
    list('availability', companyId, params),
  customers: (companyId: UUID, params: CustomerListParams) => list('customers', companyId, params),
  customerBookings: (companyId: UUID, customerId: UUID) =>
    ['customer-bookings', companyId, customerId] as const,
  services: (companyId: UUID, params: ServiceListParams) => list('services', companyId, params),
  workers: (companyId: UUID, params: object) => list('workers', companyId, params),
  workingHours: (companyId: UUID, workerId: UUID) =>
    ['working-hours', companyId, workerId] as const,
  branchWorkingHours: (companyId: UUID, branchId: UUID) =>
    ['branch-working-hours', companyId, branchId] as const,
  breaks: (companyId: UUID, workerId: UUID) => ['breaks', companyId, workerId] as const,
  timeOff: (companyId: UUID, workerId: UUID) => ['time-off', companyId, workerId] as const,
  blockedSlots: (companyId: UUID, workerId: UUID) =>
    ['blocked-slots', companyId, workerId] as const,
  salesSummary: (companyId: UUID, params: SummaryParams) =>
    list('sales-summary', companyId, params),
  cashSummary: (companyId: UUID, params: SummaryParams) => list('cash-summary', companyId, params),
  branding: (companyId: UUID) => ['branding', companyId] as const,
  inventoryProducts: (companyId: UUID, params: AssetListParams) =>
    list('inventory-products', companyId, params),
  inventoryDocuments: (companyId: UUID, params: DocumentListParams) =>
    list('inventory-documents', companyId, params),
  inventoryPhoto: (companyId: UUID, productId: UUID) =>
    ['inventory-photo', companyId, productId] as const,
  members: (companyId: UUID, params: object) => list('members', companyId, params),
  memberGrants: (companyId: UUID, membershipId: UUID) =>
    ['member-grants', companyId, membershipId] as const,
};
