import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { queryKeys } from '../../api/queryKeys';
import { publicAccountsApi } from '../../api/runtime';
import type { PublicPlan } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Skeleton } from '../../components/ui/Skeleton';
import { featureSummary, formatAmount } from '../saas/planFormat';
import { SignupDialog } from './SignupDialog';

const PERIOD_LABEL: Record<string, string> = { monthly: 'mes', yearly: 'año' };

export function PublicPricingPage() {
  const [selected, setSelected] = useState<PublicPlan | null>(null);
  const plansQuery = useQuery({
    queryKey: queryKeys.publicPlans(),
    queryFn: () => publicAccountsApi.plans(),
  });
  const plans = plansQuery.data?.results ?? [];

  return (
    <main className="min-h-screen bg-surface">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-6">
        <span className="text-sm font-semibold uppercase tracking-wide text-brand">AGENDA</span>
        <Link to="/login" className="text-sm font-medium text-ink hover:underline">
          Ya tengo cuenta
        </Link>
      </header>

      <section className="mx-auto max-w-5xl px-6 pb-6 text-center">
        <h1 className="text-3xl font-semibold text-ink">Agenda para tu negocio</h1>
        <p className="mx-auto mt-3 max-w-2xl text-muted">
          Reservas, clientes, equipo, inventario y reportes en un solo panel.
          Elige un plan y comienza hoy mismo; activa tu cuenta desde tu correo.
        </p>
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-16">
        {plansQuery.isError ? (
          <ErrorBanner message="No pudimos cargar los planes. Recarga la página." />
        ) : plansQuery.isLoading ? (
          <Skeleton rows={6} />
        ) : plans.length === 0 ? (
          <EmptyState
            title="Pronto habrá planes disponibles"
            description="Estamos preparando la contratación en línea. Vuelve a revisar en unos días."
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-3">
            {plans.map((plan) => (
              <article
                key={plan.id}
                className="flex flex-col rounded-xl border border-line bg-panel p-6 shadow-sm"
              >
                <h2 className="text-lg font-semibold text-ink">{plan.name}</h2>
                <p className="mt-1 text-sm text-muted">{plan.description}</p>
                <p className="mt-4 text-2xl font-semibold text-ink">
                  {formatAmount(plan)}
                  <span className="text-sm font-normal text-muted">
                    {' '}/ {PERIOD_LABEL[plan.billing_period] ?? plan.billing_period}
                  </span>
                </p>
                <p className="mt-1 text-sm text-muted">{plan.trial_days} días de prueba</p>
                <p className="mt-4 flex-1 text-sm text-ink">{featureSummary(plan)}</p>
                <Button className="mt-6 w-full" onClick={() => setSelected(plan)}>
                  Contratar
                </Button>
              </article>
            ))}
          </div>
        )}
      </section>

      <SignupDialog
        plan={selected}
        onOpenChange={(open) => { if (!open) setSelected(null); }}
      />
    </main>
  );
}
