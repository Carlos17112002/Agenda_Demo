import type { ApiClient } from './client';
import type { ThemeMode } from './types';

export type Branding = {
  display_name: string;
  logo_url: string;
  primary_color: string;
  secondary_color: string;
  theme_mode: ThemeMode;
  booking_url: string;
  name: string;
  slug: string;
  can_manage: boolean;
};

export type BrandingInput = {
  display_name?: string;
  slug?: string;
  primary_color?: string;
  secondary_color?: string;
  theme_mode?: ThemeMode;
};

export function createBrandingApi(client: ApiClient) {
  return {
    get: () => client.get<Branding>('/api/v1/company/branding/'),
    update: (input: BrandingInput) =>
      client.patch<Branding>('/api/v1/company/branding/', input),
    uploadLogo: (file: File) => {
      const form = new FormData();
      form.append('logo', file);
      return client.postForm<Branding>('/api/v1/company/branding/logo/', form);
    },
    removeLogo: () => client.delete<Branding>('/api/v1/company/branding/logo/'),
  };
}

export type BrandingApi = ReturnType<typeof createBrandingApi>;
