import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useLocation, useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input } from '../../components/ui/Field';
import { firstAllowedPath } from '../../lib/permissions';

const schema = z.object({
  email: z.string().min(1, 'Ingresa tu correo.').email('Ingresa un correo válido.'),
  password: z.string().min(1, 'Ingresa tu contraseña.'),
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const { status, login, can, hasFeature } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  });

  useEffect(() => {
    if (status === 'ready') {
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? firstAllowedPath(can, hasFeature), { replace: true });
    }
    if (status === 'choosingCompany') navigate('/empresa', { replace: true });
    if (status === 'saasAdmin') navigate('/saas', { replace: true });
  }, [can, hasFeature, location.state, navigate, status]);

  async function onSubmit(values: FormValues) {
    setSubmitError(null);
    try {
      await login(values.email, values.password);
    } catch (error) {
      setSubmitError(error instanceof ApiError ? error.message : 'No se pudo iniciar sesión.');
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface p-6">
      <section className="w-full max-w-sm rounded-xl border border-line bg-panel p-8 shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-wide text-brand">AGENDA</p>
        <h1 className="mt-1 text-2xl font-semibold text-ink">Panel del operador</h1>
        <p className="mt-1 text-sm text-muted">Accede con tu cuenta de la empresa.</p>

        <form className="mt-6 space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          {submitError ? <ErrorBanner message={submitError} /> : null}
          <Field label="Correo" htmlFor="login-email" error={errors.email?.message}>
            <Input
              id="login-email"
              type="email"
              autoComplete="email"
              {...register('email')}
            />
          </Field>
          <Field label="Contraseña" htmlFor="login-password" error={errors.password?.message}>
            <Input
              id="login-password"
              type="password"
              autoComplete="current-password"
              {...register('password')}
            />
          </Field>
          <Button type="submit" loading={isSubmitting} loadingLabel="Entrando…" className="w-full">
            Entrar
          </Button>
        </form>
      </section>
    </main>
  );
}
