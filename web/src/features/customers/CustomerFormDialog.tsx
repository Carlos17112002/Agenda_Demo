import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import type { Customer, CustomerInput } from '../../api/customers';
import { customersApi } from '../../api/runtime';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Textarea } from '../../components/ui/Field';

const customerSchema = z.object({
  first_name: z.string().trim().min(2, 'Ingresa al menos 2 caracteres.'),
  last_name: z.string().trim().max(120, 'Máximo 120 caracteres.'),
  email: z
    .string()
    .trim()
    .refine(
      (value) => value === '' || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
      'Ingresa un correo válido.',
    ),
  phone: z.string().trim().max(32, 'Máximo 32 caracteres.'),
  document_id: z.string().trim().max(32, 'Máximo 32 caracteres.'),
  notes: z.string().max(2000, 'Máximo 2000 caracteres.'),
  active: z.boolean(),
});

type CustomerFormValues = z.infer<typeof customerSchema>;

const FIELD_NAMES = [
  'first_name',
  'last_name',
  'email',
  'phone',
  'document_id',
  'notes',
] as const;

function valuesFrom(customer: Customer | null): CustomerFormValues {
  return {
    first_name: customer?.first_name ?? '',
    last_name: customer?.last_name ?? '',
    email: customer?.email ?? '',
    phone: customer?.phone ?? '',
    document_id: customer?.document_id ?? '',
    notes: customer?.notes ?? '',
    active: customer?.active ?? true,
  };
}

export function CustomerFormDialog({
  open,
  customer,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  customer: Customer | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<CustomerFormValues>({
    resolver: zodResolver(customerSchema),
    defaultValues: valuesFrom(customer),
  });

  const mutation = useMutation({
    mutationFn: (values: CustomerInput) =>
      customer ? customersApi.update(customer.id, values) : customersApi.create(values),
    onSuccess: () => {
      onSaved();
      onOpenChange(false);
    },
    onError: (error) => {
      if (!(error instanceof ApiError) || !error.fields) return;
      Object.entries(error.fields).forEach(([field, messages]) => {
        if ((FIELD_NAMES as readonly string[]).includes(field)) {
          setError(field as (typeof FIELD_NAMES)[number], { message: messages[0] });
        }
      });
    },
  });

  const onSubmit = handleSubmit((values) => {
    mutation.mutate(values);
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onOpenChange(false);
      }}
      title={customer ? 'Editar cliente' : 'Nuevo cliente'}
      description="Los datos de contacto se usan para confirmar y recordar reservas."
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {mutation.error ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudo guardar el cliente.'
            }
          />
        ) : null}

        <FormRow>
          <Field label="Nombre" htmlFor="customer-first-name" error={errors.first_name?.message}>
            <Input id="customer-first-name" autoComplete="given-name" {...register('first_name')} />
          </Field>
          <Field label="Apellido" htmlFor="customer-last-name" error={errors.last_name?.message}>
            <Input id="customer-last-name" autoComplete="family-name" {...register('last_name')} />
          </Field>
        </FormRow>

        <FormRow>
          <Field label="Correo" htmlFor="customer-email" error={errors.email?.message}>
            <Input id="customer-email" type="email" autoComplete="email" {...register('email')} />
          </Field>
          <Field label="Teléfono" htmlFor="customer-phone" error={errors.phone?.message}>
            <Input id="customer-phone" type="tel" autoComplete="tel" {...register('phone')} />
          </Field>
        </FormRow>

        <Field label="Documento" htmlFor="customer-document" error={errors.document_id?.message}>
          <Input id="customer-document" {...register('document_id')} />
        </Field>

        <Field label="Notas" htmlFor="customer-notes" error={errors.notes?.message}>
          <Textarea id="customer-notes" rows={3} {...register('notes')} />
        </Field>

        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" className="h-4 w-4 accent-brand" {...register('active')} />
          Cliente activo
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending} loadingLabel="Guardando…">
            Guardar cliente
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
