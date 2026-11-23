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
  is_superuser?: boolean;
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

export type SaasSubscription = {
  id: UUID;
  plan: string;
  status: string;
  effective_status: string;
  usable: boolean;
  current_period_end: ISODateTime | null;
  trial_ends_at: ISODateTime | null;
};

export type SaasCompany = {
  id: UUID;
  name: string;
  slug: string;
  legal_name: string;
  tax_identifier: string;
  status: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  subscription: SaasSubscription | null;
};

export type SaasPlanFeature = {
  code: string;
  enabled: boolean;
  limit_value: number | null;
};

export type SaasPlan = {
  id: UUID;
  code: string;
  name: string;
  description: string;
  price: string;
  currency: string;
  billing_period: 'monthly' | 'yearly';
  trial_days: number;
  active: boolean;
  is_default: boolean;
  sort_order: number;
  features: SaasPlanFeature[];
};

export type SaasPlanFeatureInput = {
  code: string;
  enabled: boolean;
  limit_value?: number | null;
};

export type SaasPlanInput = {
  code: string;
  name: string;
  description: string;
  price: string;
  currency: string;
  billing_period: 'monthly' | 'yearly';
  trial_days: number;
  active: boolean;
  is_default: boolean;
  features: SaasPlanFeatureInput[];
};

export type SaasCompanyCreateInput = {
  company_name: string;
  slug: string;
  email: string;
  first_name?: string;
  password?: string;
  plan?: string;
  trial_days?: number;
};

export type SaasCompanyCreateResult = {
  company_id: UUID;
  company_name: string;
  slug: string;
  owner_id: UUID;
  owner_email: string;
  owner_name: string;
  temporary_password: string;
  booking_url: string;
  subscription: SaasSubscription | null;
  detail: string;
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

export type PublicPlanFeature = {
  code: string;
  enabled: boolean;
  limit_value: number | null;
};

export type PublicPlan = {
  id: UUID;
  code: string;
  name: string;
  description: string;
  price: string;
  currency: string;
  billing_period: 'monthly' | 'yearly';
  trial_days: number;
  is_default: boolean;
  features: PublicPlanFeature[];
};

export type RegisterCompanyInput = {
  company_name: string;
  email: string;
  password: string;
  first_name?: string;
  plan?: string;
};

export type RegisterCompanyResponse = {
  company_id: UUID;
  company_name: string;
  email: string;
  detail: string;
};

export type VerifyEmailResponse = {
  access: string;
  refresh: string;
  user: User;
};
