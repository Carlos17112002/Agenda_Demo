import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { saasApi } from '../../api/runtime';
import type { SaasPlan } from '../../api/types';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { PageHeader } from '../../components/ui/PageHeader';
import { Skeleton } from '../../components/ui/Skeleton';
import { PLAN_FEATURES } from './planFeatures';
import { SaasPlanFormDialog } from './SaasPlanFormDialog';

const PERIOD_LABEL: Record<string, string> = { monthly: 'mes', yearly: 'año' };
const FEATURE_BY_CODE = new Map(PLAN_FEATURES.map((feature) => [feature.code, feature]));

function formatAmount(plan: SaasPlan): string {
  const amount = Number(plan.price);
  const formatted = Number.isFinite(amount)
    ? amount.toLocaleString('es-CL', { maximumFractionDigits: 2 })
    : plan.price;
  return `${plan.currency} ${formatted}`;
}

function featureSummary(plan: SaasPlan): string {
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

export function SaasPlansPage() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<SaasPlan | null>(null);

  const plansQuery = useQuery({
    queryKey: ['saas-plans'],
    queryFn: () => saasApi.plans(),
  });

  const rows = plansQuery.data?.results ?? [];

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['saas-plans'] });
  };

  return (
    <section>
      <PageHeader
        title="Planes"
        description="Define precios, días de prueba y funcionalidades; las nuevas empresas se crean con estos planes."
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            Nuevo plan
          </Button>
        }
      />

      {plansQuery.error ? (
        <ErrorBanner
          message="No se pudieron cargar los planes."
          onRetry={() => void plansQuery.refetch()}
        />
      ) : null}

      {plansQuery.isPending ? <Skeleton rows={4} /> : null}

      {plansQuery.isSuccess && rows.length === 0 ? (
        <EmptyState
          title="Todavía no hay planes."
          description="Crea el primer plan para que las empresas puedan suscribirse."
        />
      ) : null}

      {rows.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-line bg-panel">
          <table className="min-w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3">Plan</th>
                <th className="px-4 py-3">Precio</th>
                <th className="px-4 py-3">Prueba</th>
                <th className="px-4 py-3">Funcionalidades</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((plan) => (
                <tr key={plan.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 font-medium text-ink">
                      {plan.name}
                      {plan.is_default ? <Badge tone="active">Predeterminado</Badge> : null}
                    </div>
                    <div className="text-xs text-muted">{plan.code}</div>
                  </td>
                  <td className="px-4 py-3">{formatAmount(plan)}</td>
                  <td className="px-4 py-3">
                    <div>{plan.trial_days > 0 ? `${plan.trial_days} días` : 'Sin prueba'}</div>
                    <div className="text-xs text-muted">
                      por {PERIOD_LABEL[plan.billing_period] ?? plan.billing_period}
                    </div>
                  </td>
                  <td className="px-4 py-3">{featureSummary(plan)}</td>
                  <td className="px-4 py-3">
                    <Badge tone={plan.active ? 'active' : 'inactive'}>
                      {plan.active ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setEditing(plan);
                        setFormOpen(true);
                      }}
                    >
                      Editar
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <SaasPlanFormDialog
        open={formOpen}
        plan={editing}
        onOpenChange={(next) => {
          setFormOpen(next);
          if (!next) setEditing(null);
        }}
        onSaved={invalidate}
      />
    </section>
  );
}
