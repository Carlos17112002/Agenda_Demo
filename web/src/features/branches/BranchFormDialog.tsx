import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import type { BranchInput } from '../../api/branches';
import { ApiError } from '../../api/client';
import { branchesApi } from '../../api/runtime';
import type { Branch } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Select } from '../../components/ui/Field';
import { TIMEZONES } from './timezones';

const schema = z.object({
  name: z.string().trim().min(1, 'Ingresa el nombre.').max(120, 'Máximo 120 caracteres.'),
  code: z
    .string()
    .trim()
    .min(1, 'Ingresa el código.')
    .max(32, 'Máximo 32 caracteres.')
    .regex(/^[A-Za-z0-9._-]+$/, 'Usa letras, números, punto, guion o guion bajo.'),
  address: z.string().trim().max(240, 'Máximo 240 caracteres.'),
  timezone: z.string().min(1, 'Selecciona una zona horaria.'),
});

type FormValues = z.infer<typeof schema>;

function valuesFrom(branch: Branch | null): FormValues {
  return {
    name: branch?.name ?? '',
    code: branch?.code ?? '',
    address: branch?.address ?? '',
    timezone: branch?.timezone ?? 'America/Santiago',
  };
}

export function BranchFormDialog({
  open,
  branch,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  branch: Branch | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: valuesFrom(branch),
  });

  useEffect(() => {
    if (open) reset(valuesFrom(branch));
  }, [open, branch, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) => {
      const input: BranchInput = {
        name: values.name,
        code: values.code,
        address: values.address,
        timezone: values.timezone,
      };
      return branch ? branchesApi.update(branch.id, input) : branchesApi.create(input);
    },
    onSuccess: () => {
      onOpenChange(false);
      onSaved();
    },
    onError: (error) => {
      if (!(error instanceof ApiError) || !error.fields) return;
      (['name', 'code', 'address', 'timezone'] as const).forEach((field) => {
        const messages = error.fields?.[field];
        if (messages) setError(field, { message: messages[0] });
      });
    },
  });

  const onSubmit = handleSubmit((values) => mutation.mutate(values));

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={branch ? 'Editar sucursal' : 'Nueva sucursal'}
      description="Las sucursales organizan la agenda y los equipos de cada local."
      wide
    >
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        {mutation.error && !(mutation.error instanceof ApiError && mutation.error.fields) ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudo guardar la sucursal.'
            }
          />
        ) : null}

        <FormRow>
          <Field label="Nombre" htmlFor="branch-name" error={errors.name?.message}>
            <Input id="branch-name" {...register('name')} />
          </Field>
          <Field label="Código" htmlFor="branch-code" error={errors.code?.message}>
            <Input id="branch-code" {...register('code')} />
          </Field>
        </FormRow>

        <FormRow>
          <Field label="Dirección" htmlFor="branch-address" error={errors.address?.message}>
            <Input id="branch-address" {...register('address')} />
          </Field>
          <Field label="Zona horaria" htmlFor="branch-timezone" error={errors.timezone?.message}>
            <Select id="branch-timezone" {...register('timezone')}>
              {TIMEZONES.map((timezone) => (
                <option key={timezone} value={timezone}>
                  {timezone}
                </option>
              ))}
            </Select>
          </Field>
        </FormRow>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending} loadingLabel="Guardando…">
            {branch ? 'Guardar cambios' : 'Crear sucursal'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
