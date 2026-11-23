import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import type { Resolver } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import type { Service, ServiceInput } from '../../api/services';
import { servicesApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Textarea } from '../../components/ui/Field';

const serviceSchema = z.object({
  name: z.string().trim().min(2, 'Ingresa al menos 2 caracteres.').max(160, 'Máximo 160 caracteres.'),
  description: z.string().max(2000, 'Máximo 2000 caracteres.'),
  duration_minutes: z.coerce
    .number()
    .int('Usa minutos enteros.')
    .min(5, 'La duración mínima es 5 minutos.')
    .max(480, 'La duración máxima es 480 minutos.'),
  price: z
    .string()
    .trim()
    .regex(/^\d+(\.\d{1,2})?$/, 'Usa un monto como 12000 o 12000.50.'),
  buffer_before_minutes: z.coerce
    .number()
    .int('Usa minutos enteros.')
    .min(0, 'El buffer no puede ser negativo.')
    .max(120, 'El buffer máximo es 120 minutos.'),
  buffer_after_minutes: z.coerce
    .number()
    .int('Usa minutos enteros.')
    .min(0, 'El buffer no puede ser negativo.')
    .max(120, 'El buffer máximo es 120 minutos.'),
  branches: z.array(z.string()),
  active: z.boolean(),
});

type ServiceFormValues = z.infer<typeof serviceSchema>;

const FIELD_NAMES = [
  'name',
  'description',
  'duration_minutes',
  'price',
  'buffer_before_minutes',
  'buffer_after_minutes',
  'branches',
] as const;

function valuesFrom(service: Service | null): ServiceFormValues {
  return {
    name: service?.name ?? '',
    description: service?.description ?? '',
    duration_minutes: service?.duration_minutes ?? 30,
    price: service?.price ?? '0',
    buffer_before_minutes: service?.buffer_before_minutes ?? 0,
    buffer_after_minutes: service?.buffer_after_minutes ?? 0,
    branches: service?.branches ?? [],
    active: service?.active ?? true,
  };
}

export function ServiceFormDialog({
  open,
  service,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  service: Service | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const { bootstrap } = useAuth();
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);
  const {
    register,
    handleSubmit,
    setError,
    setValue,
    watch,
    formState: { errors },
  } = useForm<ServiceFormValues>({
    resolver: zodResolver(serviceSchema) as Resolver<ServiceFormValues>,
    defaultValues: valuesFrom(service),
  });
  const selectedBranches = watch('branches');

  const mutation = useMutation({
    mutationFn: (values: ServiceInput) =>
      service ? servicesApi.update(service.id, values) : servicesApi.create(values),
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

  function toggleBranch(branchId: string, checked: boolean) {
    const next = checked
      ? [...selectedBranches, branchId]
      : selectedBranches.filter((id) => id !== branchId);
    setValue('branches', next, { shouldValidate: true });
  }

  const onSubmit = handleSubmit((values) => {
    mutation.mutate(values);
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onOpenChange(false);
      }}
      title={service ? 'Editar servicio' : 'Nuevo servicio'}
      description="La duración y los buffers determinan los cupos que ofrece la agenda."
      wide
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {mutation.error ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudo guardar el servicio.'
            }
          />
        ) : null}

        <Field label="Nombre" htmlFor="service-name" error={errors.name?.message}>
          <Input id="service-name" {...register('name')} />
        </Field>

        <Field label="Descripción" htmlFor="service-description" error={errors.description?.message}>
          <Textarea id="service-description" rows={2} {...register('description')} />
        </Field>

        <FormRow>
          <Field
            label="Duración (minutos)"
            htmlFor="service-duration"
            error={errors.duration_minutes?.message}
            hint="Entre 5 y 480 minutos."
          >
            <Input
              id="service-duration"
              type="number"
              min={5}
              max={480}
              step={5}
              {...register('duration_minutes')}
            />
          </Field>
          <Field label="Precio" htmlFor="service-price" error={errors.price?.message}>
            <Input id="service-price" inputMode="decimal" {...register('price')} />
          </Field>
        </FormRow>

        <FormRow>
          <Field
            label="Buffer antes (minutos)"
            htmlFor="service-buffer-before"
            error={errors.buffer_before_minutes?.message}
          >
            <Input
              id="service-buffer-before"
              type="number"
              min={0}
              max={120}
              {...register('buffer_before_minutes')}
            />
          </Field>
          <Field
            label="Buffer después (minutos)"
            htmlFor="service-buffer-after"
            error={errors.buffer_after_minutes?.message}
          >
            <Input
              id="service-buffer-after"
              type="number"
              min={0}
              max={120}
              {...register('buffer_after_minutes')}
            />
          </Field>
        </FormRow>

        <fieldset>
          <legend className="mb-1 block text-sm font-medium text-ink">Sucursales</legend>
          <p className="mb-2 text-xs text-muted">
            Sin selección, el servicio está disponible en todas las sucursales.
          </p>
          <div className="flex flex-wrap gap-3">
            {branches.map((branch) => (
              <label key={branch.id} className="flex items-center gap-2 text-sm text-ink">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-brand"
                  checked={selectedBranches.includes(branch.id)}
                  onChange={(event) => toggleBranch(branch.id, event.target.checked)}
                />
                {branch.name}
              </label>
            ))}
          </div>
          {errors.branches?.message ? (
            <p role="alert" className="mt-1 text-xs text-danger">
              {errors.branches.message}
            </p>
          ) : null}
        </fieldset>

        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" className="h-4 w-4 accent-brand" {...register('active')} />
          Servicio activo
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending} loadingLabel="Guardando…">
            Guardar servicio
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
