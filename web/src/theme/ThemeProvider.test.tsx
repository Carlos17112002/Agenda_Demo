import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, test } from 'vitest';

import { ThemeProvider, useTheme } from './ThemeProvider';

function Probe() {
  const { mode, toggleMode } = useTheme();
  return <button onClick={toggleMode}>{mode}</button>;
}

describe('ThemeProvider', () => {
  test('usa el tema de la empresa cuando no hay preferencia', () => {
    render(
      <ThemeProvider companyMode="dark">
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByRole('button', { name: 'dark' })).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement).toHaveClass('dark');
  });

  test('la preferencia guardada manda sobre el tema de la empresa', () => {
    sessionStorage.setItem('agenda.web.theme', 'light');
    render(
      <ThemeProvider companyMode="dark">
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByRole('button', { name: 'light' })).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  test('alternar el tema persiste la preferencia', async () => {
    render(
      <ThemeProvider companyMode="light">
        <Probe />
      </ThemeProvider>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'light' }));
    expect(screen.getByRole('button', { name: 'dark' })).toBeInTheDocument();
    expect(sessionStorage.getItem('agenda.web.theme')).toBe('dark');
  });
});
