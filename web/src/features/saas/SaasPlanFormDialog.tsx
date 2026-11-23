import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import { saasApi } from '../../api/runtime';
import type { SaasPlan, SaasPlanInput } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Select, Textarea } from '../../components/ui/Field';
import { PLAN_FEATURES } from './planFeatures';

const schema = z.object({
  name: z.string().trim().min(1, 'Ingresa el nombre del plan.').max(120, 'Máximo 120 caracteres.'),
  code: z
    .string()
    .trim()
    .min(1, 'Ingresa el código.')
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, 'Usa minúsculas, números y guiones.'),
  description: z.string().trim().max(500, 'Máximo 500 caracteres.'),
  price: z
    .string()
    .trim()
    .refine(
      (value) => value === '' || /^\d+(?:\.\d{1,2})?$/.test(value),
      'Usa un monto válido, por ejemplo 19990.',
    ),
  currency: z.string().trim().regex(/^[A-Za-z]{3}$/, 'Usa un código de 3 letras, por ejemplo CLP.'),
  billing_period: z.enum(['monthly', 'yearly']),
  trial_days: z
    .string()
    .trim()
    .regex(/^\d+$/, 'Usa un número entero.')
    .refine((value) => Number(value) <= 365, 'Máximo 365 días.'),
  active: z.boolean(),
  is_default: z.boolean(),
});

type FormValues = z.infer<typeof schema>;
type FeatureState = Record<string, { enabled: boolean; limit: string }>;

function valuesFrom(plan: SaasPlan | null): FormValues {
  return {
    name: plan?.name ?? '',
    code: plan?.code ?? '',
    description: plan?.description ?? '',
    price: plan?.price ?? '',
    currency: plan?.currency ?? 'CLP',
    billing_period: plan?.billing_period ?? 'monthly',
    trial_days: String(plan?.trial_days ?? 0),
    active: plan?.active ?? true,
    is_default: plan?.is_default ?? false,
  };
}

function featuresFrom(plan: SaasPlan | null): FeatureState {
  return Object.fromEntries(
    PLAN_FEATURES.map((feature) => {
      const current = plan?.features.find((item) => item.code === feature.code);
      return [
        feature.code,
        {
          enabled: current?.enabled ?? false,
          limit: current?.limit_value != null ? String(current.limit_value) : '',
        },
      ];
    }),
  );
}

export function SaasPlanFormDialog({
  open,
  plan,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  plan: SaasPlan | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const [features, setFeatures] = useState<FeatureState>(() => featuresFrom(plan));
  const [featureError, setFeatureError] = useState('');
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: valuesFrom(plan),
  });

  useEffect(() => {
    if (!open) return;
    reset(valuesFrom(plan));
    setFeatures(featuresFrom(plan));
    setFeatureError('');
  }, [open, plan, reset]);

  const mutation = useMutation({
    mutationFn: (input: SaasPlanInput) =>
      plan ? saasApi.updatePlan(plan.id, input) : saasApi.createPlan(input),
    onSuccess: () => {
      onOpenChange(false);
      onSaved();
    },
    onError: (error) => {
      if (!(error instanceof ApiError) || !error.fields) return;
      (['name', 'code', 'price', 'currency', 'billing_period', 'trial_days'] as const).forEach(
        (field) => {
          const messages = error.fields?.[field];
          if (messages) setError(field, { message: messages[0] });
        },
      );
    },
  });

  const submit = handleSubmit((values) => {
    const invalidLimit = PLAN_FEATURES.some(
      (feature) =>
        feature.limitLabel &&
        features[feature.code]?.enabled &&
        features[feature.code].limit !== '' &&
        !/^\d+$/.test(features[feature.code].limit),
    );
    if (invalidLimit) {
      setFeatureError('Usa un número entero en los límites.');
      return;
    }
    setFeatureError('');
    mutation.mutate({
      code: values.code,
      name: values.name,
      description: values.description,
      price: values.price || '0',
      currency: values.currency.toUpperCase(),
      billing_period: values.billing_period,
      trial_days: Number(values.trial_days || 0),
      active: values.active,
      is_default: values.is_default,
      features: PLAN_FEATURES.filter((feature) => features[feature.code]?.enabled).map(
        (feature) => ({
          code: feature.code,
          enabled: true,
          limit_value:
            feature.limitLabel && features[feature.code].limit !== ''
              ? Number(features[feature.code].limit)
              : null,
        }),
      ),
    });
  });

  const updateFeature = (code: string, patch: Partial<{ enabled: boolean; limit: string }>) => {
    setFeatures((current) => ({ ...current, [code]: { ...current[code], ...patch } }));
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={plan ? 'Editar plan' : 'Nuevo plan'}
      description="Los planes definen el precio, la prueba y las funcionalidades de cada empresa."
      wide
    >
      <form className="space-y-4" onSubmit={submit} noValidate>
        {mutation.error && !(mutation.error instanceof ApiError && mutation.error.fields) ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudo guardar el plan.'
            }
          />
        ) : null}

        <FormRow>
          <Field label="Nombre" htmlFor="saas-plan-name" error={errors.name?.message}>
            <Input id="saas-plan-name" {...register('name')} />
          </Field>
          <Field label="Código" htmlFor="saas-plan-code" error={errors.code?.message}>
            <Input id="saas-plan-code" {...register('code')} />
          </Field>
        </FormRow>

        <Field label="Descripción" htmlFor="saas-plan-description" error={errors.description?.message}>
          <Textarea id="saas-plan-description" {...register('description')} />
        </Field>

        <FormRow>
          <Field label="Precio" htmlFor="saas-plan-price" error={errors.price?.message}>
            <Input id="saas-plan-price" inputMode="decimal" {...register('price')} />
          </Field>
          <Field label="Moneda" htmlFor="saas-plan-currency" error={errors.currency?.message}>
            <Input id="saas-plan-currency" {...register('currency')} />
          </Field>
        </FormRow>

        <FormRow>
          <Field label="Período" htmlFor="saas-plan-period" error={errors.billing_period?.message}>
            <Select id="saas-plan-period" {...register('billing_period')}>
              <option value="monthly">Mensual</option>
              <option value="yearly">Anual</option>
            </Select>
          </Field>
          <Field label="Días de prueba" htmlFor="saas-plan-trial" error={errors.trial_days?.message}>
            <Input id="saas-plan-trial" inputMode="numeric" {...register('trial_days')} />
          </Field>
        </FormRow>

        <div className="flex flex-wrap gap-4">
          <label className="flex items-center gap-2 text-sm text-ink">
            <input type="checkbox" className="h-4 w-4 accent-brand" {...register('active')} />
            Activo
          </label>
          <label className="flex items-center gap-2 text-sm text-ink">
            <input type="checkbox" className="h-4 w-4 accent-brand" {...register('is_default')} />
            Predeterminado para nuevas empresas
          </label>
        </div>

        <fieldset className="rounded-lg border border-line bg-panel p-4">
          <legend className="px-1 text-sm font-medium text-ink">Funcionalidades</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            {PLAN_FEATURES.map((feature) => {
              const state = features[feature.code];
              return (
                <div key={feature.code} className="space-y-1">
                  <label className="flex items-center gap-2 text-sm text-ink">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-brand"
                      checked={state?.enabled ?? false}
                      onChange={(event) =>
                        updateFeature(feature.code, { enabled: event.target.checked })
                      }
                    />
                    {feature.label}
                  </label>
                  {feature.limitLabel ? (
                    <Input
                      aria-label={feature.limitLabel}
                      inputMode="numeric"
                      value={state?.limit ?? ''}
                      disabled={!state?.enabled}
                      onChange={(event) => updateFeature(feature.code, { limit: event.target.value })}
                    />
                  ) : null}
                </div>
              );
            })}
          </div>
          {featureError ? (
            <p role="alert" className="mt-2 text-xs text-danger">
              {featureError}
            </p>
          ) : null}
        </fieldset>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending} loadingLabel="Guardando…">
            {plan ? 'Guardar cambios' : 'Crear plan'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
