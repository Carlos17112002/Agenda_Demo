import { useQueryClient } from '@tanstack/react-query';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import { ApiError } from '../api/client';
import type {
  Bootstrap,
  BootstrapCompany,
  CompanySummary,
  LoginResponse,
  PasswordChangeResponse,
  RefreshResponse,
  TenantContextResponse,
  User,
} from '../api/types';
import { allows } from '../lib/permissions';
import type { SessionStore } from './sessionStore';

export type AuthStatus = 'loading' | 'anonymous' | 'choosingCompany' | 'saasAdmin' | 'ready';

export type AuthGateway = {
  login(email: string, password: string): Promise<LoginResponse>;
  refresh(refresh: string): Promise<RefreshResponse>;
  me(): Promise<User>;
  companies(): Promise<CompanySummary[]>;
  createContext(companyId: string): Promise<TenantContextResponse>;
  bootstrap(): Promise<Bootstrap>;
  logout(refresh: string): Promise<void>;
  changePassword(current: string, next: string): Promise<PasswordChangeResponse>;
};

type Runtime = {
  accessToken: string | null;
  tenantContextId: string | null;
};

export type AuthContextValue = {
  status: AuthStatus;
  isSaasAdmin: boolean;
  user: User | null;
  companies: CompanySummary[];
  company: BootstrapCompany | null;
  bootstrap: Bootstrap | null;
  permissions: string[];
  error: string | null;
  login(email: string, password: string): Promise<void>;
  selectCompany(company: CompanySummary): Promise<void>;
  logout(): Promise<void>;
  refreshBootstrap(): Promise<void>;
  changePassword(currentPassword: string, newPassword: string): Promise<void>;
  can(required: string): boolean;
  hasFeature(code: string): boolean;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Ocurrió un error inesperado.';
}

const SUSPENDED_MESSAGE = 'Tu empresa está suspendida. Contacta al administrador.';

function isAccessible(company: CompanySummary): boolean {
  return company.status === 'trial' || company.status === 'active';
}

export function isSaasAdminUser(user: User | null): boolean {
  return Boolean(user && (user.is_saas_admin || user.is_superuser));
}

type Props = {
  children: ReactNode;
  gateway: AuthGateway;
  store: SessionStore;
  runtime: Runtime;
};

export function AuthProvider({ children, gateway, store, runtime }: Props) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<User | null>(null);
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [company, setCompany] = useState<BootstrapCompany | null>(null);
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [error, setError] = useState<string | null>(null);
  // El refresh rota el token: dos intentos concurrentes con el mismo valor
  // dejan la sesión inválida (el segundo recibe 401 y la borra).
  const bootRefresh = useRef<Promise<RefreshResponse> | null>(null);

  const refreshBootTokens = useCallback(
    (refresh: string) => {
      if (!bootRefresh.current) {
        bootRefresh.current = gateway.refresh(refresh).finally(() => {
          bootRefresh.current = null;
        });
      }
      return bootRefresh.current;
    },
    [gateway],
  );

  const clearLocalSession = useCallback(() => {
    runtime.accessToken = null;
    runtime.tenantContextId = null;
    store.clear();
    queryClient.clear();
    setUser(null);
    setCompanies([]);
    setCompany(null);
    setBootstrap(null);
    setError(null);
  }, [queryClient, runtime, store]);

  const applyBootstrap = useCallback((data: Bootstrap) => {
    setUser(data.user);
    setCompany(data.company);
    setBootstrap(data);
  }, []);

  const activateCompany = useCallback(
    async (target: CompanySummary) => {
      setStatus('loading');
      setError(null);
      const context = await gateway.createContext(target.id);
      runtime.tenantContextId = context.id;
      store.writeSession({
        companyId: target.id,
        contextId: context.id,
        companyName: target.display_name || target.name,
      });
      queryClient.clear();
      const data = await gateway.bootstrap();
      applyBootstrap(data);
      setStatus('ready');
    },
    [applyBootstrap, gateway, queryClient, runtime, store],
  );

  useEffect(() => {
    let cancelled = false;

    async function restore() {
      const refresh = store.readRefresh();
      if (!refresh) {
        if (!cancelled) setStatus('anonymous');
        return;
      }
      try {
        const tokens = await refreshBootTokens(refresh);
        if (cancelled) return;
        runtime.accessToken = tokens.access;
        if (tokens.refresh) store.writeRefresh(tokens.refresh);

        const current = await gateway.me();
        if (cancelled) return;
        if (isSaasAdminUser(current)) {
          setUser(current);
          setStatus('saasAdmin');
          return;
        }

        const all = await gateway.companies();
        if (cancelled) return;
        const list = all.filter(isAccessible);
        setCompanies(list);

        const stored = store.readSession();
        if (stored) {
          const match = list.find((item) => item.id === stored.companyId);
          if (match) {
            runtime.tenantContextId = stored.contextId;
            try {
              const data = await gateway.bootstrap();
              if (cancelled) return;
              applyBootstrap(data);
              setStatus('ready');
              return;
            } catch (restoreError) {
              if (!(restoreError instanceof ApiError) || ![401, 403].includes(restoreError.status)) {
                throw restoreError;
              }
              runtime.tenantContextId = null;
              store.writeSession(null);
            }
          } else {
            store.writeSession(null);
          }
        }

        if (list.length === 1) {
          await activateCompany(list[0]);
          return;
        }
        if (list.length === 0) {
          clearLocalSession();
          setStatus('anonymous');
          setError(all.length > 0 ? SUSPENDED_MESSAGE : 'La cuenta no tiene empresas activas.');
          return;
        }
        runtime.tenantContextId = null;
        setStatus('choosingCompany');
      } catch (restoreError) {
        if (cancelled) return;
        clearLocalSession();
        setStatus('anonymous');
        if (restoreError instanceof ApiError && restoreError.status !== 401) {
          setError(restoreError.message);
        }
      }
    }

    void restore();
    return () => {
      cancelled = true;
    };
  }, [activateCompany, applyBootstrap, clearLocalSession, gateway, refreshBootTokens, runtime, store]);

  const login = useCallback(
    async (email: string, password: string) => {
      setStatus('loading');
      setError(null);
      try {
        const data = await gateway.login(email, password);
        runtime.accessToken = data.access;
        store.writeRefresh(data.refresh);
        setUser(data.user);
        if (isSaasAdminUser(data.user)) {
          runtime.tenantContextId = null;
          store.writeSession(null);
          setStatus('saasAdmin');
          return;
        }
        const all = await gateway.companies();
        const list = all.filter(isAccessible);
        setCompanies(list);
        if (list.length === 1) {
          await activateCompany(list[0]);
        } else if (list.length === 0) {
          clearLocalSession();
          setStatus('anonymous');
          setError(all.length > 0 ? SUSPENDED_MESSAGE : 'La cuenta no tiene empresas activas.');
        } else {
          runtime.tenantContextId = null;
          store.writeSession(null);
          setStatus('choosingCompany');
        }
      } catch (loginError) {
        runtime.accessToken = null;
        store.writeRefresh(null);
        setError(messageOf(loginError));
        setStatus('anonymous');
        throw loginError;
      }
    },
    [activateCompany, clearLocalSession, gateway, runtime, store],
  );

  const selectCompany = useCallback(
    async (target: CompanySummary) => {
      try {
        await activateCompany(target);
      } catch (selectError) {
        setError(messageOf(selectError));
        setStatus(company ? 'ready' : 'choosingCompany');
        throw selectError;
      }
    },
    [activateCompany, company],
  );

  const logout = useCallback(async () => {
    const refresh = store.readRefresh();
    try {
      if (refresh) await gateway.logout(refresh);
    } catch {
      // El cierre local manda aunque el servidor no responda.
    }
    clearLocalSession();
    setStatus('anonymous');
  }, [clearLocalSession, gateway, store]);

  const refreshBootstrap = useCallback(async () => {
    const [data, list] = await Promise.all([gateway.bootstrap(), gateway.companies()]);
    applyBootstrap(data);
    setCompanies(list.filter(isAccessible));
  }, [applyBootstrap, gateway]);

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      const data = await gateway.changePassword(currentPassword, newPassword);
      runtime.accessToken = data.access;
      store.writeRefresh(data.refresh);
      await refreshBootstrap();
    },
    [gateway, refreshBootstrap, runtime, store],
  );

  useEffect(() => {
    const handler = () => {
      clearLocalSession();
      setStatus('anonymous');
    };
    window.addEventListener('agenda:session-expired', handler);
    return () => window.removeEventListener('agenda:session-expired', handler);
  }, [clearLocalSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      isSaasAdmin: isSaasAdminUser(user),
      user,
      companies,
      company,
      bootstrap,
      permissions: bootstrap?.permissions ?? [],
      error,
      login,
      selectCompany,
      logout,
      refreshBootstrap,
      changePassword,
      can: (required) => allows(bootstrap?.permissions ?? [], required),
      hasFeature: (code) => bootstrap?.features[code] ?? false,
    }),
    [
      bootstrap,
      changePassword,
      companies,
      company,
      error,
      login,
      logout,
      refreshBootstrap,
      selectCompany,
      status,
      user,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth debe usarse dentro de AuthProvider.');
  return value;
}
