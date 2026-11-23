import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, test, vi } from 'vitest';

import type { Branding } from '../../api/branding';
import { brandingApi } from '../../api/runtime';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { BrandingPage } from './BrandingPage';

const branding: Branding = {
  display_name: 'Estudio Aurora',
  logo_url: '/media/logo.png',
  primary_color: '#10B981',
  secondary_color: '#065F46',
  theme_mode: 'light',
  booking_url: '/b/estudio-aurora/',
  name: 'Estudio Aurora',
  slug: 'estudio-aurora',
  can_manage: true,
};

function renderPage(refreshBootstrap = vi.fn().mockResolvedValue(undefined)) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue({ refreshBootstrap })}>
      <QueryClientProvider client={queryClient}>
        <BrandingPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
  return { refreshBootstrap };
}

function brandingHandler(payload: Branding = branding) {
  return http.get('http://api.test/api/v1/company/branding/', () => HttpResponse.json(payload));
}

describe('BrandingPage', () => {
  afterEach(() => vi.restoreAllMocks());

  test('muestra la marca actual y la vista previa', async () => {
    server.use(brandingHandler());
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Vista previa' })).toBeInTheDocument();
    expect(screen.getAllByText('Estudio Aurora').length).toBeGreaterThan(0);
    expect(screen.getByText('/b/estudio-aurora/')).toBeInTheDocument();
    expect(screen.getByAltText('Logo de Estudio Aurora')).toHaveAttribute(
      'src',
      '/media/logo.png',
    );
  });

  test('guarda la marca y refresca el bootstrap', async () => {
    let body: unknown;
    server.use(
      brandingHandler(),
      http.patch('http://api.test/api/v1/company/branding/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...branding, display_name: 'Aurora Studio' });
      }),
    );
    const { refreshBootstrap } = renderPage();

    await screen.findByRole('heading', { name: 'Vista previa' });
    await userEvent.clear(screen.getByLabelText('Nombre visible'));
    await userEvent.type(screen.getByLabelText('Nombre visible'), 'Aurora Studio');
    await userEvent.selectOptions(screen.getByLabelText('Tema'), 'dark');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() =>
      expect(body).toMatchObject({
        display_name: 'Aurora Studio',
        slug: 'estudio-aurora',
        primary_color: '#10B981',
        secondary_color: '#065F46',
        theme_mode: 'dark',
      }),
    );
    expect(await screen.findByText('Marca actualizada.')).toBeInTheDocument();
    expect(refreshBootstrap).toHaveBeenCalled();
  });

  test('muestra el error del identificador ocupado', async () => {
    server.use(
      brandingHandler(),
      http.patch('http://api.test/api/v1/company/branding/', () =>
        HttpResponse.json(
          { slug: ['Este identificador de empresa ya está ocupado.'] },
          { status: 400 },
        ),
      ),
    );
    renderPage();

    await screen.findByRole('heading', { name: 'Vista previa' });
    await userEvent.clear(screen.getByLabelText('Identificador'));
    await userEvent.type(screen.getByLabelText('Identificador'), 'aurora');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    expect(
      await screen.findByText('Este identificador de empresa ya está ocupado.'),
    ).toBeInTheDocument();
  });

  test('sube el logo seleccionado y refresca la vista previa', async () => {
    // Node 24's fetch no reconoce el FormData de jsdom (otro realm); el
    // multipart real se cubre en domain.test.ts y en el E2E.
    let uploaded: File | null = null;
    let current = { ...branding };
    server.use(http.get('http://api.test/api/v1/company/branding/', () => HttpResponse.json(current)));
    vi.spyOn(brandingApi, 'uploadLogo').mockImplementation(async (file) => {
      uploaded = file;
      current = { ...current, logo_url: '/media/logo-nuevo.png' };
      return current;
    });
    renderPage();

    await screen.findByRole('heading', { name: 'Vista previa' });
    const file = new File(['png'], 'logo-nuevo.png', { type: 'image/png' });
    await userEvent.upload(screen.getByLabelText('Logo'), file);
    await userEvent.click(screen.getByRole('button', { name: 'Subir logo' }));

    await waitFor(() => expect(uploaded?.name).toBe('logo-nuevo.png'));
    expect(await screen.findByAltText('Logo de Estudio Aurora')).toHaveAttribute(
      'src',
      '/media/logo-nuevo.png',
    );
  });

  test('elimina el logo actual', async () => {
    let removed = false;
    server.use(
      brandingHandler(),
      http.delete('http://api.test/api/v1/company/branding/logo/', () => {
        removed = true;
        return HttpResponse.json({ ...branding, logo_url: '' });
      }),
    );
    renderPage();

    await screen.findByRole('heading', { name: 'Vista previa' });
    await userEvent.click(screen.getByRole('button', { name: 'Quitar logo' }));

    await waitFor(() => expect(removed).toBe(true));
  });
});
