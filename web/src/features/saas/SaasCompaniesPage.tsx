import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { saasApi } from '../../api/runtime';
import type { SaasCompany, SaasCompanyCreateResult } from '../../api/types';
import { Badge, type BadgeTone } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { PageHeader } from '../../components/ui/PageHeader';
import { SaasCompanyCreatedDialog } from './SaasCompanyCreatedDialog';
import { SaasCompanyFormDialog } from './SaasCompanyFormDialog';
import { SaasEditCompanyDialog } from './SaasEditCompanyDialog';

const STATUS_LABEL: Record<string, string> = {
  trial: 'Prueba',
  active: 'Activa',
  suspended: 'Suspendida',
  closed: 'Cerrada',
};

function statusTone(status: string): BadgeTone {
  if (status === 'active') return 'active';
  if (status === 'trial') return 'scheduled';
  return 'inactive';
}

export function SaasCompaniesPage() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [created, setCreated] = useState<SaasCompanyCreateResult | null>(null);
  const [editing, setEditing] = useState<SaasCompany | null>(null);

  const companiesQuery = useQuery({
    queryKey: ['saas-companies'],
    queryFn: () => saasApi.companies(),
  });
  const plansQuery = useQuery({
    queryKey: ['saas-plans'],
    queryFn: () => saasApi.plans(),
  });

  const plans = plansQuery.data?.results ?? [];
  const planName = (code: string) => plans.find((plan) => plan.code === code)?.name ?? code;
  const rows: SaasCompany[] = companiesQuery.data?.results ?? [];

  return (
    <section>
      <PageHeader
        title="Empresas"
        description="Crea empresas, entrega el acceso a su propietario y revisa el estado de su suscripción."
        actions={<Button onClick={() => setFormOpen(true)}>Nueva empresa</Button>}
      />

      {companiesQuery.error ? (
        <ErrorBanner
          message="No se pudieron cargar las empresas."
          onRetry={() => void companiesQuery.refetch()}
        />
      ) : null}
      {plansQuery.error ? (
        <ErrorBanner
          message="No se pudieron cargar los planes."
          onRetry={() => void plansQuery.refetch()}
        />
      ) : null}

      {companiesQuery.isSuccess && rows.length === 0 ? (
        <EmptyState
          title="Todavía no hay empresas."
          description="Crea la primera empresa y entrega la clave temporal a su propietario."
        />
      ) : null}

      {rows.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-line bg-panel">
          <table className="min-w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3">Empresa</th>
                <th className="px-4 py-3">Plan</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Fin del período</th>
                <th className="px-4 py-3">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((company) => (
                <tr key={company.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-3">
                    <div className="font-medium text-ink">{company.name}</div>
                    <div className="text-xs text-muted">{company.slug}</div>
                  </td>
                  <td className="px-4 py-3">
                    {company.subscription ? planName(company.subscription.plan) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={statusTone(company.status)}>
                      {STATUS_LABEL[company.status] ?? company.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    {company.subscription?.current_period_end?.slice(0, 10) ?? '—'}
                  </td>
                  <td className="px-4 py-3">
                    <Button variant="secondary" onClick={() => setEditing(company)}>
                      Editar
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <SaasCompanyFormDialog
        open={formOpen}
        plans={plans}
        onOpenChange={setFormOpen}
        onCreated={(result) => setCreated(result)}
      />

      <SaasCompanyCreatedDialog
        open={Boolean(created)}
        result={created}
        onOpenChange={(next) => {
          if (!next) setCreated(null);
        }}
      />

      <SaasEditCompanyDialog
        open={Boolean(editing)}
        company={editing}
        plans={plans}
        onOpenChange={(next) => {
          if (!next) setEditing(null);
        }}
        onSaved={() => {
          void queryClient.invalidateQueries({ queryKey: ['saas-companies'] });
        }}
      />
    </section>
  );
}
