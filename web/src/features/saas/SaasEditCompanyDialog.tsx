import { useMutation } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { ApiError } from '../../api/client';
import { saasApi } from '../../api/runtime';
import type { SaasCompany, SaasPlan } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Select } from '../../components/ui/Field';

const ACTIVE_STATUSES = ['trial', 'active'];

export function SaasEditCompanyDialog({
  open,
  company,
  plans,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  company: SaasCompany | null;
  plans: SaasPlan[];
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const currentPlanId = company?.subscription
    ? (plans.find((plan) => plan.code === company.subscription?.plan)?.id ?? '')
    : '';
  const initiallyActive = company ? ACTIVE_STATUSES.includes(company.status) : true;
  const [planId, setPlanId] = useState('');
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    if (!open || !company) return;
    setPlanId(currentPlanId);
    setIsActive(initiallyActive);
  }, [company, currentPlanId, initiallyActive, open]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!company) return;
      const requests: Promise<unknown>[] = [];
      if (isActive !== initiallyActive) {
        requests.push(saasApi.changeStatus(company.id, isActive ? 'active' : 'suspended'));
      }
      if (company.subscription && planId && planId !== currentPlanId) {
        requests.push(saasApi.changePlan(company.subscription.id, planId));
      }
      await Promise.all(requests);
    },
    onSuccess: () => {
      onOpenChange(false);
      onSaved();
    },
  });

  const selectablePlans = plans.filter((plan) => plan.active || plan.id === currentPlanId);

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Editar empresa"
      description="Ajusta el plan o suspende el acceso sin tocar los datos de la empresa."
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            Guardar cambios
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {mutation.error ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudieron guardar los cambios.'
            }
          />
        ) : null}

        <Field
          label="Plan"
          htmlFor="saas-company-plan"
          hint={
            company?.subscription ? undefined : 'La empresa no tiene una suscripción abierta.'
          }
        >
          <Select
            id="saas-company-plan"
            value={planId}
            onChange={(event) => setPlanId(event.target.value)}
            disabled={!company?.subscription}
          >
            <option value="">Selecciona un plan</option>
            {selectablePlans.map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.name}
              </option>
            ))}
          </Select>
        </Field>

        <div>
          <label
            htmlFor="saas-company-active"
            className="flex items-center gap-3 text-sm font-medium text-ink"
          >
            <input
              id="saas-company-active"
              type="checkbox"
              className="h-4 w-4 accent-brand"
              checked={isActive}
              onChange={(event) => setIsActive(event.target.checked)}
            />
            Empresa activa
          </label>
          <p className="mt-1 text-xs text-muted">
            Al desactivarla, nadie podrá ingresar al panel de esa empresa.
          </p>
        </div>
      </div>
    </Dialog>
  );
}
