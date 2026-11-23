import { PLAN_FEATURES } from './planFeatures';

export type PlanLike = {
  price: string;
  currency: string;
  features: { code: string; enabled: boolean; limit_value: number | null }[];
};

const FEATURE_BY_CODE = new Map(PLAN_FEATURES.map((feature) => [feature.code, feature]));

export function formatAmount(plan: Pick<PlanLike, 'price' | 'currency'>): string {
  const amount = Number(plan.price);
  const formatted = Number.isFinite(amount)
    ? amount.toLocaleString('es-CL', { maximumFractionDigits: 2 })
    : plan.price;
  return `${plan.currency} ${formatted}`;
}

export function featureSummary(plan: PlanLike): string {
  const enabled = plan.features.filter((feature) => feature.enabled);
  if (enabled.length === 0) return '—';
  return enabled
    .map((feature) => {
      const definition = FEATURE_BY_CODE.get(feature.code);
      const label = definition?.shortLabel ?? feature.code;
      return definition?.limitLabel && feature.limit_value != null
        ? `${label}: ${feature.limit_value}`
        : label;
    })
    .join(' · ');
}
