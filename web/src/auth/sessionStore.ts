export const REFRESH_KEY = 'agenda.web.refresh';
export const SESSION_KEY = 'agenda.web.session';

export type StoredSession = {
  companyId: string;
  contextId: string;
  companyName: string;
};

export type SessionStore = {
  readRefresh(): string | null;
  writeRefresh(value: string | null): void;
  readSession(): StoredSession | null;
  writeSession(value: StoredSession | null): void;
  clear(): void;
};

function readJson<T>(key: string): T | null {
  const raw = localStorage.getItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    localStorage.removeItem(key);
    return null;
  }
}

export const localSessionStore: SessionStore = {
  readRefresh: () => localStorage.getItem(REFRESH_KEY),
  writeRefresh: (value) => {
    if (value) localStorage.setItem(REFRESH_KEY, value);
    else localStorage.removeItem(REFRESH_KEY);
  },
  readSession: () => readJson<StoredSession>(SESSION_KEY),
  writeSession: (value) => {
    if (value) localStorage.setItem(SESSION_KEY, JSON.stringify(value));
    else localStorage.removeItem(SESSION_KEY);
  },
  clear: () => {
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(SESSION_KEY);
  },
};
