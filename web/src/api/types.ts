export type UUID = string;
export type ISODate = string;
export type ISODateTime = string;
export type ThemeMode = 'light' | 'dark';

export type User = {
  id: UUID;
  email: string;
  first_name: string;
  last_name: string;
  is_saas_admin: boolean;
  must_change_password?: boolean;
};

export type CompanySummary = {
  id: UUID;
  name: string;
  display_name: string;
  slug: string;
  logo_url: string;
  primary_color: string;
  secondary_color: string;
  theme_mode: ThemeMode;
  booking_url: string;
  status: string;
};

export type Branch = {
  id: UUID;
  company: UUID;
  name: string;
  code: string;
  address: string;
  timezone: string;
  active: boolean;
};

export type BranchRef = { id: UUID; name: string };

export type Membership = {
  id: UUID;
  role: string;
  role_display: string;
  default_branch: BranchRef | null;
};

export type BootstrapCompany = CompanySummary & {
  legal_name?: string;
  tax_identifier?: string;
};

export type Bootstrap = {
  api_version: string;
  server_time: string;
  user: User;
  company: BootstrapCompany;
  membership: Membership;
  worker: { id: UUID; name: string } | null;
  companies: CompanySummary[];
  permissions: string[];
  features: Record<string, boolean>;
  modules: Record<string, boolean>;
  billing_state: string;
  branches: Branch[];
  permission_catalog: string[];
  role_defaults: Record<string, string[]>;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type LoginResponse = {
  access: string;
  refresh: string;
  user: User;
};

export type RefreshResponse = {
  access: string;
  refresh?: string;
};

export type PasswordChangeResponse = {
  access: string;
  refresh: string;
  must_change_password: boolean;
};

export type TenantContextResponse = {
  id: string;
  company: UUID;
  company_name: string;
  expires_at: string;
};
