import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import type { Branding, BrandingInput } from '../../api/branding';
import { queryKeys } from '../../api/queryKeys';
import { brandingApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Select } from '../../components/ui/Field';
import { PageHeader } from '../../components/ui/PageHeader';
import { Skeleton } from '../../components/ui/Skeleton';
import { readableForeground } from '../../lib/colors';

const brandingSchema = z.object({
  display_name: z.string().trim().max(180, 'Máximo 180 caracteres.'),
  slug: z
    .string()
    .trim()
    .min(1, 'Ingresa el identificador.')
    .max(100, 'Máximo 100 caracteres.')
    .regex(/^[a-z0-9_-]+$/i, 'Usa letras, números, guiones o guiones bajos.'),
  primary_color: z
    .string()
    .regex(/^#[0-9A-Fa-f]{6}$/, 'Usa un color hexadecimal con formato #RRGGBB.'),
  secondary_color: z
    .string()
    .regex(/^#[0-9A-Fa-f]{6}$/, 'Usa un color hexadecimal con formato #RRGGBB.'),
  theme_mode: z.enum(['light', 'dark']),
});

type BrandingFormValues = z.infer<typeof brandingSchema>;

const LOGO_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const MAX_LOGO_BYTES = 2 * 1024 * 1024;

function valuesFrom(branding: Branding): BrandingFormValues {
  return {
    display_name: branding.display_name,
    slug: branding.slug,
    primary_color: branding.primary_color,
    secondary_color: branding.secondary_color,
    theme_mode: branding.theme_mode,
  };
}

function BrandingForm({ branding }: { branding: Branding }) {
  const { company, refreshBootstrap } = useAuth();
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState(false);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoError, setLogoError] = useState('');

  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors },
  } = useForm<BrandingFormValues>({
    resolver: zodResolver(brandingSchema),
    defaultValues: valuesFrom(branding),
  });
  const values = watch();
  const slugChanged = values.slug !== branding.slug;

  const refresh = async () => {
    await refreshBootstrap();
    void queryClient.invalidateQueries({ queryKey: queryKeys.branding(company?.id ?? '') });
  };

  const save = useMutation({
    mutationFn: (input: BrandingInput) => brandingApi.update(input),
    onSuccess: async () => {
      setSaved(true);
      await refresh();
    },
    onError: (error) => {
      setSaved(false);
      if (!(error instanceof ApiError) || !error.fields) return;
      (['display_name', 'slug', 'primary_color', 'secondary_color'] as const).forEach((field) => {
        const messages = error.fields?.[field];
        if (messages) setError(field, { message: messages[0] });
      });
    },
  });

  const uploadLogo = useMutation({
    mutationFn: (file: File) => brandingApi.uploadLogo(file),
    onSuccess: async () => {
      setLogoFile(null);
      setLogoError('');
      await refresh();
    },
  });

  const removeLogo = useMutation({
    mutationFn: () => brandingApi.removeLogo(),
    onSuccess: refresh,
  });

  const onSubmit = handleSubmit((formValues) => {
    save.mutate({ ...formValues, slug: formValues.slug.toLowerCase() });
  });

  const previewForeground = readableForeground(values.primary_color);
  const previewSurface = values.theme_mode === 'dark' ? '#0b1220' : '#f8fafc';
  const previewText = values.theme_mode === 'dark' ? '#f8fafc' : '#0f172a';

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {saved ? (
          <p role="status" className="rounded-md bg-success-soft px-4 py-3 text-sm text-success">
            Marca actualizada.
          </p>
        ) : null}
        {save.error && !(save.error instanceof ApiError && save.error.fields) ? (
          <ErrorBanner
            message={
              save.error instanceof ApiError
                ? save.error.message
                : 'No se pudo guardar la marca.'
            }
          />
        ) : null}

        <FormRow>
          <Field
            label="Nombre visible"
            htmlFor="branding-display-name"
            error={errors.display_name?.message}
            hint="Si queda vacío se usa el nombre legal de la empresa."
          >
            <Input id="branding-display-name" {...register('display_name')} />
          </Field>
          <Field
            label="Identificador"
            htmlFor="branding-slug"
            error={errors.slug?.message}
            hint="Define la dirección de la página pública."
          >
            <Input id="branding-slug" {...register('slug')} />
          </Field>
        </FormRow>

        {slugChanged ? (
          <p role="status" className="rounded-md bg-warning-soft px-4 py-3 text-sm text-warning">
            Cambiar el identificador modifica el enlace público. Los enlaces anteriores dejarán de
            funcionar.
          </p>
        ) : null}

        <FormRow>
          <Field
            label="Color primario"
            htmlFor="branding-primary"
            error={errors.primary_color?.message}
          >
            <div className="flex items-center gap-3">
              <input
                id="branding-primary"
                type="color"
                className="h-10 w-16 rounded-md border border-line bg-panel p-1"
                {...register('primary_color')}
              />
              <span className="text-sm text-muted">{values.primary_color}</span>
            </div>
          </Field>
          <Field
            label="Color secundario"
            htmlFor="branding-secondary"
            error={errors.secondary_color?.message}
          >
            <div className="flex items-center gap-3">
              <input
                id="branding-secondary"
                type="color"
                className="h-10 w-16 rounded-md border border-line bg-panel p-1"
                {...register('secondary_color')}
              />
              <span className="text-sm text-muted">{values.secondary_color}</span>
            </div>
          </Field>
        </FormRow>

        <Field label="Tema" htmlFor="branding-theme" error={errors.theme_mode?.message}>
          <Select id="branding-theme" {...register('theme_mode')}>
            <option value="light">Claro</option>
            <option value="dark">Oscuro</option>
          </Select>
        </Field>

        <div className="flex justify-end pt-2">
          <Button type="submit" loading={save.isPending} loadingLabel="Guardando…">
            Guardar cambios
          </Button>
        </div>

        <fieldset className="rounded-lg border border-line bg-panel p-4">
          <legend className="px-1 text-sm font-medium text-ink">Logo de la empresa</legend>
          <div className="flex flex-wrap items-center gap-4">
            {branding.logo_url ? (
              <img
                src={branding.logo_url}
                alt={`Logo de ${branding.display_name}`}
                className="h-16 w-16 rounded-md border border-line object-contain"
              />
            ) : (
              <div className="flex h-16 w-16 items-center justify-center rounded-md border border-dashed border-line text-xs text-muted">
                Sin logo
              </div>
            )}
            <div className="min-w-0 flex-1 space-y-2">
              <Field label="Logo" htmlFor="branding-logo" error={logoError}>
                <Input
                  id="branding-logo"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(event) => {
                    const file = event.target.files?.[0] ?? null;
                    setLogoFile(null);
                    setLogoError('');
                    if (!file) return;
                    if (!LOGO_TYPES.includes(file.type)) {
                      setLogoError('Usa PNG, JPEG o WebP.');
                      return;
                    }
                    if (file.size > MAX_LOGO_BYTES) {
                      setLogoError('El logo no puede superar 2 MB.');
                      return;
                    }
                    setLogoFile(file);
                  }}
                />
              </Field>
              <p className="text-xs text-muted">
                PNG, JPEG o WebP de hasta 2 MB y 4000 × 4000 px.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={!logoFile}
                  loading={uploadLogo.isPending}
                  loadingLabel="Subiendo…"
                  onClick={() => {
                    if (logoFile) uploadLogo.mutate(logoFile);
                  }}
                >
                  Subir logo
                </Button>
                {branding.logo_url ? (
                  <Button
                    type="button"
                    variant="ghost"
                    loading={removeLogo.isPending}
                    loadingLabel="Quitando…"
                    onClick={() => removeLogo.mutate()}
                  >
                    Quitar logo
                  </Button>
                ) : null}
              </div>
              {uploadLogo.error || removeLogo.error ? (
                <ErrorBanner
                  message={
                    uploadLogo.error instanceof ApiError
                      ? uploadLogo.error.message
                      : removeLogo.error instanceof ApiError
                        ? removeLogo.error.message
                        : 'No se pudo actualizar el logo.'
                  }
                />
              ) : null}
            </div>
          </div>
        </fieldset>
      </form>

      <aside className="rounded-lg border border-line bg-panel p-4">
        <h2 className="mb-3 text-base font-semibold text-ink">Vista previa</h2>
        <div
          className="rounded-lg p-4"
          style={{ backgroundColor: previewSurface, color: previewText }}
        >
          <div
            className="rounded-lg p-4"
            style={{ backgroundColor: values.primary_color, color: previewForeground }}
          >
            <p className="text-xs uppercase tracking-wide opacity-80">Página pública</p>
            <p className="mt-1 text-lg font-semibold">{values.display_name || branding.name}</p>
            <p className="mt-3 text-sm">Reserva tu hora en línea.</p>
            <span
              className="mt-4 inline-flex rounded-md px-3 py-2 text-xs font-semibold"
              style={{
                backgroundColor: values.secondary_color,
                color: readableForeground(values.secondary_color),
              }}
            >
              Reservar ahora
            </span>
          </div>
        </div>
        <p className="mt-3 text-xs text-muted">Enlace público actual</p>
        <p className="break-all text-sm text-ink">{branding.booking_url}</p>
        {slugChanged ? (
          <p className="mt-2 break-all text-xs text-muted">Nuevo enlace: /b/{values.slug}/</p>
        ) : null}
      </aside>
    </div>
  );
}

export function BrandingPage() {
  const { company } = useAuth();
  const query = useQuery({
    queryKey: queryKeys.branding(company?.id ?? ''),
    queryFn: () => brandingApi.get(),
    enabled: Boolean(company),
  });

  return (
    <section>
      <PageHeader
        title="Marca"
        description="Nombre, colores, tema y logo que se aplican al panel y a la página pública."
      />
      {query.isError ? (
        <ErrorBanner
          message="No se pudo cargar la marca."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {query.isPending ? <Skeleton rows={5} /> : null}
      {query.data ? <BrandingForm branding={query.data} /> : null}
    </section>
  );
}
