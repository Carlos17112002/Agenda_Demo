import { QueryClientProvider, type QueryClient } from '@tanstack/react-query';
import { useEffect, useState, type ReactNode } from 'react';
import { RouterProvider } from 'react-router-dom';

import { authGateway, sessionRuntime } from '../api/runtime';
import {
  AuthProvider,
  useAuth,
  type AuthGateway,
} from '../auth/AuthProvider';
import { localSessionStore, type SessionStore } from '../auth/sessionStore';
import { applyBrandTheme } from '../lib/colors';
import { ThemeProvider } from '../theme/ThemeProvider';
import { createQueryClient } from './queryClient';
import { router } from './router';

type Runtime = { accessToken: string | null; tenantContextId: string | null };

function ThemeHost({ children }: { children: ReactNode }) {
  const { company } = useAuth();
  return (
    <ThemeProvider companyMode={company?.theme_mode ?? 'light'}>{children}</ThemeProvider>
  );
}

function BrandThemeSync() {
  const { company } = useAuth();
  useEffect(() => {
    if (company) applyBrandTheme(company);
  }, [company]);
  return null;
}

export function AppProviders({
  children,
  gateway = authGateway,
  store = localSessionStore,
  runtime = sessionRuntime,
  queryClient,
}: {
  children?: ReactNode;
  gateway?: AuthGateway;
  store?: SessionStore;
  runtime?: Runtime;
  queryClient?: QueryClient;
}) {
  const [fallbackClient] = useState(createQueryClient);
  const client = queryClient ?? fallbackClient;

  return (
    <QueryClientProvider client={client}>
      <AuthProvider gateway={gateway} store={store} runtime={runtime}>
        <ThemeHost>
          <BrandThemeSync />
          {children ?? <RouterProvider router={router} />}
        </ThemeHost>
      </AuthProvider>
    </QueryClientProvider>
  );
}
