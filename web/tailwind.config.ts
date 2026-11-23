import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: 'var(--surface)',
        panel: 'var(--panel)',
        ink: 'var(--ink)',
        muted: 'var(--muted)',
        line: 'var(--line)',
        brand: {
          DEFAULT: 'var(--brand-primary)',
          fg: 'var(--brand-fg)',
          soft: 'var(--brand-soft)',
        },
        danger: { DEFAULT: 'var(--danger)', soft: 'var(--danger-soft)' },
        success: { DEFAULT: 'var(--success)', soft: 'var(--success-soft)' },
        warning: { DEFAULT: 'var(--warning)', soft: 'var(--warning-soft)' },
        'status-scheduled-bg': 'var(--status-scheduled-bg)',
        'status-scheduled-fg': 'var(--status-scheduled-fg)',
        'status-confirmed-bg': 'var(--status-confirmed-bg)',
        'status-confirmed-fg': 'var(--status-confirmed-fg)',
        'status-completed-bg': 'var(--status-completed-bg)',
        'status-completed-fg': 'var(--status-completed-fg)',
        'status-canceled-bg': 'var(--status-canceled-bg)',
        'status-canceled-fg': 'var(--status-canceled-fg)',
        'status-noshow-bg': 'var(--status-noshow-bg)',
        'status-noshow-fg': 'var(--status-noshow-fg)',
      },
    },
  },
  plugins: [],
} satisfies Config;
