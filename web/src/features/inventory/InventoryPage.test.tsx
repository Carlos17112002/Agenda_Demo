import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue, makeBootstrap } from '../../test/factories';
import { server } from '../../test/server';
import { InventoryPage } from './InventoryPage';

const assetFixture = {
  id: 'product-1',
  company: 'company-a',
  kind: 'asset',
  kind_display: 'Objeto',
  status: 'available',
  status_display: 'Disponible',
  sku: 'ACT-1A2B3C4D',
  name: 'Máquina de corte',
  description: '',
  category: null,
  category_name: null,
  unit: 'unit',
  unit_display: 'Unidad',
  cost: '150000.00',
  price: '0.00',
  reorder_point: '0.000',
  barcode: '',
  branch: 'branch-1',
  branch_name: 'Providencia',
  assigned_worker: 'worker-1',
  assigned_worker_name: 'Paula Rojas',
  serial_number: 'SN-001',
  internal_code: 'INT-01',
  quantity: 1,
  purchase_date: '2025-05-10',
  supplier: null,
  supplier_name: null,
  warranty_until: '2027-05-10',
  notes: '',
  photo_url: '/api/v1/inventory/products/product-1/photo/',
  photo_content_type: 'image/png',
  photo_size: 1024,
  active: true,
  created_at: '2026-11-11T12:00:00Z',
  updated_at: '2026-11-11T12:00:00Z',
};

const documentFixture = {
  id: 'document-1',
  company: 'company-a',
  client_id: null,
  name: 'Factura máquina',
  original_name: 'factura.pdf',
  content_type: 'application/pdf',
  size: 128734,
  product: 'product-1',
  product_name: 'Máquina de corte',
  product_sku: 'ACT-1A2B3C4D',
  uploaded_by_email: 'dueno@example.com',
  download_url: '/api/v1/inventory/documents/document-1/download/',
  created_at: '2026-11-11T15:00:00Z',
  updated_at: '2026-11-11T15:00:00Z',
};

function inventoryAuth(permissions: string[] = ['inventory.read']) {
  const base = makeBootstrap();
  return makeAuthValue({
    bootstrap: makeBootstrap({
      permissions,
      features: { ...base.features, inventory: true },
      modules: { ...base.modules, inventory: true },
    }),
  });
}

function renderInventory(permissions?: string[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={inventoryAuth(permissions)}>
      <QueryClientProvider client={queryClient}>
        <InventoryPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function useInventoryHandlers(urls: string[] = [], documentCount = 1) {
  server.use(
    http.get('http://api.test/api/v1/inventory/products/', ({ request }) => {
      urls.push(request.url);
      return HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [assetFixture],
      });
    }),
    http.get(
      'http://api.test/api/v1/inventory/products/product-1/photo/',
      () =>
        new HttpResponse(new Blob(['png'], { type: 'image/png' }), {
          headers: { 'Content-Type': 'image/png' },
        }),
    ),
    http.get('http://api.test/api/v1/inventory/documents/', ({ request }) => {
      urls.push(request.url);
      return HttpResponse.json({
        count: documentCount,
        next: null,
        previous: null,
        results: [documentFixture],
      });
    }),
    http.get(
      'http://api.test/api/v1/inventory/documents/document-1/download/',
      () =>
        new HttpResponse(new Blob(['%PDF-1.4'], { type: 'application/pdf' }), {
          headers: {
            'Content-Type': 'application/pdf',
            'Content-Disposition': 'attachment; filename="factura.pdf"',
          },
        }),
    ),
  );
}

describe('InventoryPage', () => {
  beforeEach(() => {
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:inventario'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  });

  afterEach(() => vi.restoreAllMocks());

  test('lista los objetos activos de la empresa', async () => {
    const urls: string[] = [];
    useInventoryHandlers(urls);
    renderInventory();

    const objects = screen.getByRole('tabpanel', { name: 'Objetos' });
    expect(await within(objects).findByText('Máquina de corte')).toBeInTheDocument();
    expect(within(objects).getByText('ACT-1A2B3C4D')).toBeInTheDocument();
    expect(within(objects).getByText('Paula Rojas')).toBeInTheDocument();
    expect(urls[0]).toContain('kind=asset');
    expect(urls[0]).toContain('active=true');
  });

  test('descarga un archivo como blob autenticado', async () => {
    useInventoryHandlers();
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {});
    renderInventory();
    await within(screen.getByRole('tabpanel', { name: 'Objetos' })).findByText(
      'Máquina de corte',
    );
    vi.mocked(URL.createObjectURL).mockClear();

    await userEvent.click(screen.getByRole('tab', { name: 'Archivos' }));
    await userEvent.click(
      await screen.findByRole('button', { name: 'Descargar Factura máquina' }),
    );

    await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
    const blobs = vi.mocked(URL.createObjectURL).mock.calls.map(([value]) => value as Blob);
    expect(blobs.some((blob) => blob.type === 'application/pdf')).toBe(true);
  });

  test('filtra objetos por búsqueda y sucursal', async () => {
    const urls: string[] = [];
    useInventoryHandlers(urls);
    renderInventory();
    await within(screen.getByRole('tabpanel', { name: 'Objetos' })).findByText(
      'Máquina de corte',
    );

    await userEvent.type(screen.getByLabelText('Buscar objeto'), 'maquina');
    await waitFor(() => expect(urls.at(-1)).toContain('search=maquina'));

    await userEvent.selectOptions(screen.getByLabelText('Sucursal'), 'branch-1');
    await waitFor(() => expect(urls.at(-1)).toContain('branch=branch-1'));
  });

  test('pagina la lista de archivos', async () => {
    const urls: string[] = [];
    useInventoryHandlers(urls, 120);
    renderInventory();
    await userEvent.click(screen.getByRole('tab', { name: 'Archivos' }));
    await screen.findByText('Factura máquina');

    const pagination = screen.getByRole('navigation', { name: 'Paginación' });
    await userEvent.click(within(pagination).getByRole('button', { name: 'Siguiente' }));

    await waitFor(() => expect(urls.at(-1)).toContain('page=2'));
  });

  test('sin permiso no consulta ni muestra datos', async () => {
    const urls: string[] = [];
    useInventoryHandlers(urls);
    renderInventory([]);

    expect(screen.getByText('Sin acceso a inventario')).toBeInTheDocument();
    expect(urls).toHaveLength(0);
  });
});
