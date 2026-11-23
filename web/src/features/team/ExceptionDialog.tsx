import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import { teamApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Select } from '../../components/ui/Field';
import { dateTimeLocalToISO, todayInZone } from '../../lib/dates';

const exceptionSchema = z
  .object({
    branch: z.string(),
    start_local: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/, 'Selecciona fecha y hora de inicio.'),
    end_local: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/, 'Selecciona fecha y hora de término.'),
    reason: z.string().trim().max(240, 'Máximo 240 caracteres.'),
  })
  .refine((values) => values.end_local > values.start_local, {
    message: 'El término debe ser posterior al inicio.',
    path: ['end_local'],
  });

type ExceptionFormValues = z.infer<typeof exceptionSchema>;

export function ExceptionDialog({
  kind,
  workerId,
  onOpenChange,
  onSaved,
}: {
  kind: 'timeOff' | 'blocked';
  workerId: string;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const { bootstrap } = useAuth();
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);
  const defaultTimezone = branches[0]?.timezone ?? 'America/Santiago';
  const today = todayInZone(defaultTimezone);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<ExceptionFormValues>({
    resolver: zodResolver(exceptionSchema),
    defaultValues: {
      branch: branches[0]?.id ?? '',
      start_local: `${today}T09:00`,
      end_local: `${today}T10:00`,
      reason: '',
    },
  });
  const selectedBranch = watch('branch');
  const timezone =
    branches.find((branch) => branch.id === selectedBranch)?.timezone ?? defaultTimezone;

  const mutation = useMutation({
    mutationFn: (values: ExceptionFormValues) => {
      const payload = {
        worker: workerId,
        branch: values.branch || null,
        starts_at: dateTimeLocalToISO(values.start_local, timezone),
        ends_at: dateTimeLocalToISO(values.end_local, timezone),
        reason: values.reason,
      };
      return kind === 'timeOff'
        ? teamApi.timeOff.create(payload)
        : teamApi.blockedSlots.create(payload);
    },
    onSuccess: () => {
      onSaved();
      onOpenChange(false);
    },
  });

  const onSubmit = handleSubmit((values) => {
    mutation.mutate(values);
  });

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onOpenChange(false);
      }}
      title={kind === 'timeOff' ? 'Nueva ausencia' : 'Nuevo bloqueo'}
      description={
        kind === 'timeOff'
          ? 'La ausencia quita cupos en el rango indicado, en una sucursal o en todas.'
          : 'El bloqueo ocupa la agenda del trabajador sin crear una reserva.'
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {mutation.error ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudo guardar el registro.'
            }
          />
        ) : null}

        <Field
          label="Sucursal"
          htmlFor="exception-branch"
          error={errors.branch?.message}
          hint={`Las horas se interpretan en la zona ${timezone}.`}
        >
          <Select id="exception-branch" {...register('branch')}>
            <option value="">Todas las sucursales</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </Select>
        </Field>

        <FormRow>
          <Field label="Inicio" htmlFor="exception-start" error={errors.start_local?.message}>
            <Input id="exception-start" type="datetime-local" {...register('start_local')} />
          </Field>
          <Field label="Término" htmlFor="exception-end" error={errors.end_local?.message}>
            <Input id="exception-end" type="datetime-local" {...register('end_local')} />
          </Field>
        </FormRow>

        <Field label="Motivo" htmlFor="exception-reason" error={errors.reason?.message}>
          <Input id="exception-reason" {...register('reason')} />
        </Field>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending} loadingLabel="Guardando…">
            {kind === 'timeOff' ? 'Guardar ausencia' : 'Guardar bloqueo'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
