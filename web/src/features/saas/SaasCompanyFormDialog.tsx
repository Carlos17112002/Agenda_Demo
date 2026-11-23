import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import { saasApi } from '../../api/runtime';
import type { SaasCompanyCreateResult, SaasPlan } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Select } from '../../components/ui/Field';
import { slugify } from './slugify';

const schema = z.object({
  company_name: z.string().min(1, 'Ingresa el nombre de la empresa.'),
  slug: z
    .string()
    .min(1, 'Ingresa un identificador.')
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, 'Usa minúsculas, números y guiones.'),
  email: z.string().min(1, 'Ingresa el correo del propietario.').email('Ingresa un correo válido.'),
  first_name: z.string(),
  password: z
    .string()
    .refine((value) => !value || value.length >= 12, 'Usa al menos 12 caracteres.'),
  plan: z.string(),
  trial_days: z
    .string()
    .refine(
      (value) => !value || (/^\d+$/.test(value) && Number(value) >= 0 && Number(value) <= 365),
      'Usa un número entre 0 y 365.',
    ),
});

type FormValues = z.infer<typeof schema>;

export function SaasCompanyFormDialog({
  open,
  plans,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  plans: SaasPlan[];
  onOpenChange: (open: boolean) => void;
  onCreated: (result: SaasCompanyCreateResult) => void;
}) {
  const slugTouched = useRef(false);
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      company_name: '',
      slug: '',
      email: '',
      first_name: '',
      password: '',
      plan: '',
      trial_days: '',
    },
  });

  const create = useMutation({
    mutationFn: (values: FormValues) =>
      saasApi.createCompany({
        company_name: values.company_name,
        slug: values.slug,
        email: values.email,
        first_name: values.first_name || undefined,
        password: values.password || undefined,
        plan: values.plan || undefined,
        trial_days: values.trial_days ? Number(values.trial_days) : undefined,
      }),
    onSuccess: (result) => {
      reset();
      slugTouched.current = false;
      onOpenChange(false);
      onCreated(result);
    },
  });

  const planValue = watch('plan');
  useEffect(() => {
    if (!planValue && plans.length > 0) setValue('plan', plans[0].code);
  }, [planValue, plans, setValue]);

  const nameField = register('company_name');
  const slugField = register('slug');

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          reset();
          slugTouched.current = false;
          create.reset();
        }
        onOpenChange(next);
      }}
      title="Nueva empresa"
      description="Se creará la empresa con un propietario. Si no indicas clave, se genera una temporal."
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            type="submit"
            form="saas-company-form"
            loading={create.isPending}
            loadingLabel="Creando…"
          >
            Crear empresa
          </Button>
        </>
      }
    >
      <form
        id="saas-company-form"
        className="space-y-4"
        onSubmit={handleSubmit((values) => create.mutate(values))}
        noValidate
      >
        {create.error ? (
          <ErrorBanner
            message={
              create.error instanceof ApiError
                ? create.error.message
                : 'No se pudo crear la empresa.'
            }
          />
        ) : null}
        <FormRow>
          <Field label="Nombre de la empresa" htmlFor="saas-company-name" error={errors.company_name?.message}>
            <Input
              id="saas-company-name"
              {...nameField}
              onChange={(event) => {
                void nameField.onChange(event);
                if (!slugTouched.current) {
                  setValue('slug', slugify(event.target.value));
                }
              }}
            />
          </Field>
          <Field
            label="Identificador"
            htmlFor="saas-company-slug"
            error={errors.slug?.message}
            hint="Se usa en la dirección pública de reservas."
          >
            <Input
              id="saas-company-slug"
              {...slugField}
              onChange={(event) => {
                slugTouched.current = true;
                void slugField.onChange(event);
              }}
            />
          </Field>
        </FormRow>
        <FormRow>
          <Field label="Correo del propietario" htmlFor="saas-company-email" error={errors.email?.message}>
            <Input id="saas-company-email" type="email" autoComplete="off" {...register('email')} />
          </Field>
          <Field label="Nombre del propietario" htmlFor="saas-company-first-name" error={errors.first_name?.message}>
            <Input id="saas-company-first-name" autoComplete="off" {...register('first_name')} />
          </Field>
        </FormRow>
        <Field
          label="Clave inicial"
          htmlFor="saas-company-password"
          error={errors.password?.message}
          hint="Opcional. Mínimo 12 caracteres; si la dejas vacía se genera una temporal."
        >
          <Input
            id="saas-company-password"
            type="text"
            autoComplete="off"
            {...register('password')}
          />
        </Field>
        <FormRow>
          <Field label="Plan" htmlFor="saas-company-plan" error={errors.plan?.message}>
            <Select id="saas-company-plan" {...register('plan')}>
              {plans.length === 0 ? <option value="">Plan por defecto</option> : null}
              {plans.map((plan) => (
                <option key={plan.id} value={plan.code}>
                  {plan.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Días de prueba" htmlFor="saas-company-trial" error={errors.trial_days?.message}>
            <Input
              id="saas-company-trial"
              inputMode="numeric"
              {...register('trial_days')}
            />
          </Field>
        </FormRow>
      </form>
    </Dialog>
  );
}
