import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import { publicAccountsApi } from '../../api/runtime';
import type { PublicPlan } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input } from '../../components/ui/Field';

const schema = z.object({
  company_name: z.string().min(2, 'Ingresa el nombre de tu empresa.'),
  first_name: z.string().max(150).optional(),
  email: z.string().min(1, 'Ingresa tu correo.').email('Ingresa un correo válido.'),
  password: z.string().min(12, 'Usa al menos 12 caracteres.'),
});

type FormValues = z.infer<typeof schema>;

type Props = {
  plan: PublicPlan | null;
  onOpenChange: (open: boolean) => void;
};

export function SignupDialog({ plan, onOpenChange }: Props) {
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);
  const [resent, setResent] = useState(false);
  const {
    register, handleSubmit, reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { company_name: '', first_name: '', email: '', password: '' },
  });

  const open = plan !== null;

  function close(next: boolean) {
    if (!next) {
      reset();
      setSubmitError(null);
      setFieldErrors({});
      setPendingEmail(null);
      setResent(false);
    }
    onOpenChange(next);
  }

  async function onSubmit(values: FormValues) {
    if (!plan) return;
    setSubmitError(null);
    setFieldErrors({});
    try {
      const result = await publicAccountsApi.registerCompany({
        company_name: values.company_name,
        first_name: values.first_name || undefined,
        email: values.email,
        password: values.password,
        plan: plan.code,
      });
      setPendingEmail(result.email);
    } catch (error) {
      if (error instanceof ApiError) {
        setSubmitError(error.message);
        if (error.fields) setFieldErrors(error.fields);
      } else {
        setSubmitError('No se pudo crear la cuenta. Intenta nuevamente.');
      }
    }
  }

  async function resend() {
    if (!pendingEmail) return;
    setResent(false);
    setSubmitError(null);
    try {
      await publicAccountsApi.resendVerification(pendingEmail);
      setResent(true);
    } catch {
      setSubmitError('No se pudo reenviar el enlace. Intenta nuevamente.');
    }
  }

  const errorFor = (name: keyof FormValues) =>
    fieldErrors[name]?.[0] ?? errors[name]?.message;

  return (
    <Dialog
      open={open}
      onOpenChange={close}
      title={pendingEmail ? 'Revisa tu correo' : `Contratar plan ${plan?.name ?? ''}`}
      description={
        pendingEmail
          ? `Enviamos un enlace de activación a ${pendingEmail}. Ábrelo para entrar a tu panel.`
          : 'Crea la cuenta de tu empresa. Te enviaremos un correo para activarla.'
      }
    >
      {pendingEmail ? (
        <div className="space-y-4">
          {resent ? <p className="text-sm text-ink">Enviamos un nuevo enlace.</p> : null}
          {submitError ? <ErrorBanner message={submitError} /> : null}
          <Button type="button" variant="secondary" onClick={resend} className="w-full">
            Reenviar enlace
          </Button>
        </div>
      ) : (
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          {submitError ? <ErrorBanner message={submitError} /> : null}
          <Field label="Nombre de la empresa" htmlFor="signup-company" error={errorFor('company_name')}>
            <Input id="signup-company" {...register('company_name')} />
          </Field>
          <Field label="Tu nombre" htmlFor="signup-name" error={errorFor('first_name')}>
            <Input id="signup-name" autoComplete="given-name" {...register('first_name')} />
          </Field>
          <Field label="Correo" htmlFor="signup-email" error={errorFor('email')}>
            <Input id="signup-email" type="email" autoComplete="email" {...register('email')} />
          </Field>
          <Field label="Contraseña" htmlFor="signup-password" error={errorFor('password')}>
            <Input
              id="signup-password" type="password" autoComplete="new-password"
              {...register('password')}
            />
          </Field>
          <Button type="submit" loading={isSubmitting} loadingLabel="Creando cuenta…" className="w-full">
            Crear cuenta
          </Button>
        </form>
      )}
    </Dialog>
  );
}
