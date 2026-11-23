import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import type { Member, MemberInput, MemberRole, MemberUpdateInput } from '../../api/members';
import { membersApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Select } from '../../components/ui/Field';
import { MEMBER_ROLES } from './memberRoles';

const schema = z.object({
  email: z.string().trim().email('Ingresa un correo válido.'),
  first_name: z.string().trim().max(150, 'Máximo 150 caracteres.'),
  last_name: z.string().trim().max(150, 'Máximo 150 caracteres.'),
  role: z.string().min(1, 'Selecciona un rol.'),
  default_branch: z.string(),
  create_worker_profile: z.boolean(),
});

type FormValues = z.infer<typeof schema>;

function valuesFrom(member: Member | null): FormValues {
  return {
    email: member?.email ?? '',
    first_name: member?.first_name ?? '',
    last_name: member?.last_name ?? '',
    role: member?.role ?? 'reception',
    default_branch: member?.default_branch?.id ?? '',
    create_worker_profile: false,
  };
}

export function MemberFormDialog({
  open,
  member,
  onOpenChange,
  onSaved,
  onCreated,
}: {
  open: boolean;
  member: Member | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
  onCreated: (email: string, password: string) => void;
}) {
  const { bootstrap, user } = useAuth();
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);
  const isOwner = bootstrap?.membership.role === 'owner';
  const roles = MEMBER_ROLES.filter(
    (item) => isOwner || (item.value !== 'owner' && item.value !== 'admin'),
  );
  const {
    register,
    handleSubmit,
    setError,
    reset,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: valuesFrom(member),
  });
  const role = watch('role');

  useEffect(() => {
    if (open) reset(valuesFrom(member));
  }, [open, member, reset]);

  const mutation = useMutation({
    mutationFn: async (values: FormValues) => {
      if (member) {
        const input: MemberUpdateInput = {
          first_name: values.first_name,
          last_name: values.last_name,
          role: values.role as MemberRole,
          default_branch: values.default_branch || null,
        };
        return { kind: 'updated' as const, member: await membersApi.update(member.id, input) };
      }
      const input: MemberInput = {
        email: values.email,
        first_name: values.first_name,
        last_name: values.last_name,
        role: values.role as MemberRole,
        default_branch: values.default_branch || null,
        create_worker_profile: values.create_worker_profile,
      };
      return { kind: 'created' as const, result: await membersApi.create(input) };
    },
    onSuccess: (result) => {
      onSaved();
      onOpenChange(false);
      if (result.kind === 'created') {
        onCreated(result.result.member.email, result.result.temporary_password);
      }
    },
    onError: (error) => {
      if (!(error instanceof ApiError) || !error.fields) return;
      Object.entries(error.fields).forEach(([field, messages]) => {
        if (field === 'email' || field === 'default_branch' || field === 'role') {
          setError(field, { message: messages[0] });
        }
      });
    },
  });

  const onSubmit = handleSubmit((values) => {
    if (member && member.role === 'owner' && user?.id === member.user_id) {
      return;
    }
    mutation.mutate(values);
  });

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={member ? 'Editar usuario' : 'Nuevo usuario'}
      description="El local predeterminado se usa al abrir la agenda, pero puede cambiarse."
      wide
    >
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        {mutation.error && !(mutation.error instanceof ApiError && mutation.error.fields) ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudo guardar el usuario.'
            }
          />
        ) : null}

        <FormRow>
          <Field label="Correo" htmlFor="member-email" error={errors.email?.message}>
            <Input
              id="member-email"
              type="email"
              autoComplete="email"
              disabled={Boolean(member)}
              {...register('email')}
            />
          </Field>
          <Field label="Rol" htmlFor="member-role" error={errors.role?.message}>
            <Select id="member-role" {...register('role')}>
              {roles.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </Select>
          </Field>
        </FormRow>

        <FormRow>
          <Field label="Nombre" htmlFor="member-first-name" error={errors.first_name?.message}>
            <Input id="member-first-name" autoComplete="given-name" {...register('first_name')} />
          </Field>
          <Field label="Apellido" htmlFor="member-last-name" error={errors.last_name?.message}>
            <Input id="member-last-name" autoComplete="family-name" {...register('last_name')} />
          </Field>
        </FormRow>

        <Field
          label="Local predeterminado"
          htmlFor="member-branch"
          hint="Si se desactiva o elimina, la agenda usará el primer local activo."
          error={errors.default_branch?.message}
        >
          <Select id="member-branch" {...register('default_branch')}>
            <option value="">Sin local predeterminado</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </Select>
        </Field>

        {!member && role === 'worker' ? (
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              className="h-4 w-4 accent-brand"
              {...register('create_worker_profile')}
            />
            Crear también el perfil de trabajador en el local
          </label>
        ) : null}

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending} loadingLabel="Guardando…">
            {member ? 'Guardar cambios' : 'Crear usuario'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
