import type { ReactNode } from 'react';

export type BadgeTone =
  | 'scheduled'
  | 'confirmed'
  | 'completed'
  | 'canceled'
  | 'no_show'
  | 'active'
  | 'inactive';

const tones: Record<BadgeTone, string> = {
  scheduled: 'bg-status-scheduled-bg text-status-scheduled-fg',
  confirmed: 'bg-status-confirmed-bg text-status-confirmed-fg',
  completed: 'bg-status-completed-bg text-status-completed-fg',
  canceled: 'bg-status-canceled-bg text-status-canceled-fg',
  no_show: 'bg-status-noshow-bg text-status-noshow-fg',
  active: 'bg-success-soft text-success',
  inactive: 'bg-status-completed-bg text-status-completed-fg',
};

export function Badge({ tone, children }: { tone: BadgeTone; children: ReactNode }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}
