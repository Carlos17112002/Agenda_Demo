import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import type { Worker, WorkerInput } from '../../api/team';
import { teamApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input } from '../../components/ui/Field';

const workerSchema = z.object({
  first_name: z.string().trim().min(2, 'Ingresa al menos 2 caracteres.').max(120, 'Máximo 120 caracteres.'),
  last_name: z.string().trim().max(120, 'Máximo 120 caracteres.'),
  email: z
    .string()
    .trim()
    .refine(
      (value) => value === '' || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
      'Ingresa un correo válido.',
    ),
  phone: z.string().trim().max(32, 'Máximo 32 caracteres.'),
  job_title: z.string().trim().max(120, 'Máximo 120 caracteres.'),
  color: z.string().regex(/^#[0-9a-fA-F]{6}$/, 'Usa un color hexadecimal como #10B981.'),
  branches: z.array(z.string()).min(1, 'Selecciona al menos una sucursal.'),
  active: z.boolean(),
});

type WorkerFormValues = z.infer<typeof workerSchema>;

const FIELD_NAMES = [
  'first_name',
  'last_name',
  'email',
  'phone',
  'job_title',
  'color',
  'branches',
] as const;

function valuesFrom(worker: Worker | null): WorkerFormValues {
  return {
    first_name: worker?.first_name ?? '',
    last_name: worker?.last_name ?? '',
    email: worker?.email ?? '',
    phone: worker?.phone ?? '',
    job_title: worker?.job_title ?? '',
    color: worker?.color ?? '#10B981',
    branches: worker?.branches ?? [],
    active: worker?.active ?? true,
  };
}

export function WorkerFormDialog({
  open,
  worker,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  worker: Worker | null;
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
  } = useForm<WorkerFormValues>({
    resolver: zodResolver(workerSchema),
    defaultValues: valuesFrom(worker),
  });
  const selectedBranches = watch('branches');
  const color = watch('color');

  const mutation = useMutation({
    mutationFn: (values: WorkerInput) =>
      worker ? teamApi.workers.update(worker.id, values) : teamApi.workers.create(values),
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
    mutation.mutate({ ...values, membership: worker?.membership ?? null });
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onOpenChange(false);
      }}
      title={worker ? 'Editar trabajador' : 'Nuevo trabajador'}
      description="El trabajador recibe cupos solo en las sucursales seleccionadas."
      wide
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {mutation.error ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudo guardar el trabajador.'
            }
          />
        ) : null}

        <FormRow>
          <Field label="Nombre" htmlFor="worker-first-name" error={errors.first_name?.message}>
            <Input id="worker-first-name" autoComplete="given-name" {...register('first_name')} />
          </Field>
          <Field label="Apellido" htmlFor="worker-last-name" error={errors.last_name?.message}>
            <Input id="worker-last-name" autoComplete="family-name" {...register('last_name')} />
          </Field>
        </FormRow>

        <FormRow>
          <Field label="Correo" htmlFor="worker-email" error={errors.email?.message}>
            <Input id="worker-email" type="email" autoComplete="email" {...register('email')} />
          </Field>
          <Field label="Teléfono" htmlFor="worker-phone" error={errors.phone?.message}>
            <Input id="worker-phone" type="tel" autoComplete="tel" {...register('phone')} />
          </Field>
        </FormRow>

        <FormRow>
          <Field label="Cargo" htmlFor="worker-job-title" error={errors.job_title?.message}>
            <Input id="worker-job-title" {...register('job_title')} />
          </Field>
          <Field label="Color" htmlFor="worker-color" error={errors.color?.message}>
            <div className="flex items-center gap-3">
              <input
                id="worker-color"
                type="color"
                className="h-10 w-16 rounded-md border border-line bg-panel p-1"
                {...register('color')}
              />
              <span className="text-sm text-muted">{color}</span>
            </div>
          </Field>
        </FormRow>

        <fieldset>
          <legend className="mb-1 block text-sm font-medium text-ink">Sucursales</legend>
          <p className="mb-2 text-xs text-muted">
            La agenda solo ofrece cupos del trabajador en estas sucursales.
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
          Trabajador activo
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending} loadingLabel="Guardando…">
            Guardar trabajador
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
