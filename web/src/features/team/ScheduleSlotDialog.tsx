import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import type { Resolver } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import { teamApi } from '../../api/runtime';
import type { Break, Weekday, WorkingHours } from '../../api/team';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Select } from '../../components/ui/Field';
import { WEEKDAYS } from '../../lib/format';

const slotSchema = z
  .object({
    branch: z.string().min(1, 'Selecciona una sucursal.'),
    weekday: z.coerce.number().int().min(0).max(6),
    start_time: z
      .string()
      .regex(/^([01]\d|2[0-3]):[0-5]\d$/, 'Usa el formato HH:MM.'),
    end_time: z
      .string()
      .regex(/^([01]\d|2[0-3]):[0-5]\d$/, 'Usa el formato HH:MM.'),
    label: z.string().trim().max(120, 'Máximo 120 caracteres.'),
  })
  .refine((values) => values.end_time > values.start_time, {
    message: 'La hora de término debe ser posterior al inicio.',
    path: ['end_time'],
  });

type SlotFormValues = z.infer<typeof slotSchema>;

export function ScheduleSlotDialog({
  kind,
  workerId,
  branchIds,
  onOpenChange,
  onSaved,
}: {
  kind: 'hours' | 'break';
  workerId: string;
  branchIds: string[];
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const { bootstrap } = useAuth();
  const branches = (bootstrap?.branches ?? []).filter(
    (branch) => branch.active && branchIds.includes(branch.id),
  );
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SlotFormValues>({
    resolver: zodResolver(slotSchema) as Resolver<SlotFormValues>,
    defaultValues: {
      branch: branches[0]?.id ?? '',
      weekday: 0,
      start_time: kind === 'break' ? '12:00' : '09:00',
      end_time: kind === 'break' ? '13:00' : '18:00',
      label: kind === 'break' ? 'Almuerzo' : '',
    },
  });

  const mutation = useMutation({
    mutationFn: (values: SlotFormValues): Promise<WorkingHours | Break> => {
      const payload = {
        worker: workerId,
        branch: values.branch,
        weekday: values.weekday as Weekday,
        start_time: values.start_time,
        end_time: values.end_time,
      };
      return kind === 'hours'
        ? teamApi.workingHours.create(payload)
        : teamApi.breaks.create({ ...payload, label: values.label });
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
      title={kind === 'hours' ? 'Agregar horario' : 'Agregar pausa'}
      description={
        kind === 'hours'
          ? 'El turno se repite cada semana en la sucursal elegida.'
          : 'La pausa se excluye de los cupos disponibles.'
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {mutation.error ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudo guardar el bloque.'
            }
          />
        ) : null}

        <Field label="Sucursal" htmlFor="slot-branch" error={errors.branch?.message}>
          <Select id="slot-branch" {...register('branch')}>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </Select>
        </Field>

        <FormRow>
          <Field label="Día" htmlFor="slot-weekday" error={errors.weekday?.message}>
            <Select id="slot-weekday" {...register('weekday')}>
              {WEEKDAYS.map((label, index) => (
                <option key={label} value={index}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          {kind === 'break' ? (
            <Field label="Etiqueta" htmlFor="slot-label" error={errors.label?.message}>
              <Input id="slot-label" {...register('label')} />
            </Field>
          ) : null}
        </FormRow>

        <FormRow>
          <Field label="Inicio" htmlFor="slot-start" error={errors.start_time?.message}>
            <Input id="slot-start" type="time" {...register('start_time')} />
          </Field>
          <Field label="Término" htmlFor="slot-end" error={errors.end_time?.message}>
            <Input id="slot-end" type="time" {...register('end_time')} />
          </Field>
        </FormRow>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            type="submit"
            loading={mutation.isPending}
            loadingLabel="Guardando…"
          >
            {kind === 'hours' ? 'Guardar horario' : 'Guardar pausa'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
