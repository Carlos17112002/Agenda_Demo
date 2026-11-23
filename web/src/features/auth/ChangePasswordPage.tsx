import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input } from '../../components/ui/Field';
import { firstAllowedPath } from '../../lib/permissions';

const schema = z
  .object({
    current_password: z.string().min(1, 'Ingresa tu contraseña actual.'),
    new_password: z.string().min(12, 'Usa al menos 12 caracteres.'),
    confirm_password: z.string().min(1, 'Repite la nueva contraseña.'),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    message: 'Las contraseñas no coinciden.',
    path: ['confirm_password'],
  });

type FormValues = z.infer<typeof schema>;

export function ChangePasswordPage() {
  const { changePassword, can, hasFeature } = useAuth();
  const navigate = useNavigate();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await changePassword(values.current_password, values.new_password);
      navigate(firstAllowedPath(can, hasFeature), { replace: true });
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : 'No se pudo cambiar la contraseña.';
      setError('root', { message });
    }
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-md items-center px-6">
      <section className="w-full rounded-lg border border-line bg-panel p-8">
        <h1 className="text-xl font-semibold text-ink">Cambia tu contraseña</h1>
        <p className="mt-2 text-sm text-muted">
          Usaste una clave temporal. Define una contraseña propia para continuar.
        </p>
        <form className="mt-6 space-y-4" onSubmit={onSubmit} noValidate>
          {errors.root?.message ? <ErrorBanner message={errors.root.message} /> : null}
          <Field
            label="Contraseña actual"
            htmlFor="password-current"
            error={errors.current_password?.message}
          >
            <Input
              id="password-current"
              type="password"
              autoComplete="current-password"
              {...register('current_password')}
            />
          </Field>
          <Field
            label="Nueva contraseña"
            htmlFor="password-new"
            error={errors.new_password?.message}
          >
            <Input
              id="password-new"
              type="password"
              autoComplete="new-password"
              {...register('new_password')}
            />
          </Field>
          <Field
            label="Repetir contraseña"
            htmlFor="password-confirm"
            error={errors.confirm_password?.message}
          >
            <Input
              id="password-confirm"
              type="password"
              autoComplete="new-password"
              {...register('confirm_password')}
            />
          </Field>
          <Button type="submit" loading={isSubmitting} loadingLabel="Actualizando…">
            Actualizar contraseña
          </Button>
        </form>
      </section>
    </main>
  );
}
