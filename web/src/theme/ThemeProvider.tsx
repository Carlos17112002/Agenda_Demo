import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import type { ThemeMode } from '../api/types';

const STORAGE_KEY = 'agenda.web.theme';

type ThemeContextValue = {
  mode: ThemeMode;
  preference: ThemeMode | null;
  setMode(mode: ThemeMode): void;
  toggleMode(): void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readPreference(): ThemeMode | null {
  const value = sessionStorage.getItem(STORAGE_KEY);
  return value === 'light' || value === 'dark' ? value : null;
}

export function ThemeProvider({
  children,
  companyMode = 'light',
}: {
  children: ReactNode;
  companyMode?: ThemeMode;
}) {
  const [preference, setPreference] = useState<ThemeMode | null>(readPreference);
  const mode = preference ?? companyMode;

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = mode;
    root.classList.toggle('dark', mode === 'dark');
    root.style.colorScheme = mode;
  }, [mode]);

  const setMode = useCallback((next: ThemeMode) => {
    sessionStorage.setItem(STORAGE_KEY, next);
    setPreference(next);
  }, []);

  const toggleMode = useCallback(() => {
    setMode(mode === 'dark' ? 'light' : 'dark');
  }, [mode, setMode]);

  const value = useMemo<ThemeContextValue>(
    () => ({ mode, preference, setMode, toggleMode }),
    [mode, preference, setMode, toggleMode],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext);
  if (!value) throw new Error('useTheme debe usarse dentro de ThemeProvider.');
  return value;
}
