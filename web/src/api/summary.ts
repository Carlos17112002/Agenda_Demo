import type { ApiClient } from './client';
import type { ISODate, UUID } from './types';

export type ReportRange = {
  date_from: ISODate | null;
  date_to: ISODate | null;
  timezone: string;
  branch: UUID | null;
  worker: UUID | null;
};

export type BookingCounts = {
  total: number;
  scheduled: number;
  confirmed: number;
  completed: number;
  canceled: number;
  no_show: number;
};

export type SalesTotals = {
  sales: number;
  subtotal: string;
  discounts: string;
  total: string;
  paid: string;
  cost: string;
  profit: string;
  margin_percent: string;
  average_ticket: string;
  bookings: BookingCounts;
};

export type PaymentMethodTotal = {
  method: string;
  method_display: string;
  count: number;
  amount: string;
};

export type SalesDay = {
  date: ISODate;
  sales: number;
  subtotal: string;
  discounts: string;
  total: string;
  cost: string;
  profit: string;
};

export type BranchTotal = {
  branch: UUID;
  branch_name: string;
  sales: number;
  subtotal: string;
  discounts: string;
  total: string;
  cost: string;
};

export type TopItem = {
  product?: UUID;
  service?: UUID;
  description: string;
  sku: string | null;
  quantity: string;
  total: string;
  cost: string;
  profit: string;
};

export type WorkerTotal = {
  worker: UUID | null;
  worker_name: string;
  bookings: BookingCounts;
  sales: number;
  total: string;
  profit: string;
};

export type SalesSummary = {
  range: ReportRange;
  totals: SalesTotals;
  by_payment_method: PaymentMethodTotal[];
  by_day: SalesDay[];
  by_branch: BranchTotal[];
  by_worker: WorkerTotal[];
  top_products: TopItem[];
  top_services: TopItem[];
};

export type CashTotals = {
  sessions: number;
  open: number;
  closed: number;
  opening: string;
  cash_sales: string;
  cash_expenses: string;
  expected: string;
  closing: string;
  difference: string;
  expenses: string;
};

export type CashSessionRow = {
  id: UUID;
  number: string;
  branch: UUID;
  branch_name: string;
  status: string;
  opened_at: string;
  closed_at: string | null;
  opening_amount: string;
  cash_sales: string;
  cash_expenses: string;
  expected: string;
  closing_amount: string | null;
  difference: string | null;
};

export type ExpenseTotal = { category: string; total: string };
export type ExpenseMethodTotal = { method: string; method_display: string; total: string };

export type CashSummary = {
  range: ReportRange;
  totals: CashTotals;
  sessions: CashSessionRow[];
  expenses_by_category: ExpenseTotal[];
  expenses_by_method: ExpenseMethodTotal[];
};

export type SummaryParams = {
  date_from: ISODate;
  date_to: ISODate;
  branch?: UUID;
  worker?: UUID;
};

export type ExportFormat = 'pdf' | 'excel';
export type ExportParams = SummaryParams & { fmt: ExportFormat };

export function createSummaryApi(client: ApiClient) {
  return {
    sales: (params: SummaryParams) =>
      client.get<SalesSummary>('/api/v1/reports/sales-summary/', { ...params }),
    cash: (params: SummaryParams) =>
      client.get<CashSummary>('/api/v1/reports/cash-summary/', { ...params }),
    export: (params: ExportParams) =>
      client.download('/api/v1/reports/export/', { ...params }),
  };
}

export type SummaryApi = ReturnType<typeof createSummaryApi>;
