import type { Branch } from '../../api/types';

export function pickInitialBranchId(
  branches: Branch[],
  preferred: string | null | undefined,
): string {
  const active = branches.filter((branch) => branch.active);
  if (preferred) {
    const match = active.find((branch) => branch.id === preferred);
    if (match) return match.id;
  }
  return active[0]?.id ?? '';
}
