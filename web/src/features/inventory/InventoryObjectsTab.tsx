import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import type { AssetStatus, InventoryProduct } from '../../api/inventory';
import { queryKeys } from '../../api/queryKeys';
import { inventoryApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select } from '../../components/ui/Field';
import { Pagination } from '../../components/ui/Pagination';
import { Skeleton } from '../../components/ui/Skeleton';
import { formatDateLabel } from '../../lib/dates';
import { useDebouncedValue } from '../../lib/useDebouncedValue';

const STATUS_OPTIONS: { value: AssetStatus | ''; label: string }[] = [
  { value: '', label: 'Todos los estados' },
  { value: 'available', label: 'Disponible' },
  { value: 'assigned', label: 'Asignado' },
  { value: 'maintenance', label: 'En mantenimiento' },
  { value: 'retired', label: 'Dado de baja' },
];

function AssetPhoto({ product }: { product: InventoryProduct }) {
  const { company } = useAuth();
  const [url, setUrl] = useState<string | null>(null);
  const photoQuery = useQuery({
    queryKey: queryKeys.inventoryPhoto(company?.id ?? '', product.id),
    queryFn: () => inventoryApi.productPhoto(product.photo_url),
    enabled: Boolean(company && product.photo_url),
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (!photoQuery.data) {
      setUrl(null);
      return;
    }
    const objectUrl = URL.createObjectURL(photoQuery.data.blob);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [photoQuery.data]);

  const fallback = (
    <span
      aria-hidden="true"
      className="flex h-10 w-10 items-center justify-center rounded-md bg-surface text-sm font-semibold text-muted"
    >
      {product.name.slice(0, 1).toUpperCase()}
    </span>
  );

  if (!product.photo_url || photoQuery.isError) {
    return fallback;
  }

  if (url) {
    return (
      <img
        src={url}
        alt={`Foto de ${product.name}`}
        className="h-10 w-10 rounded-md object-cover"
      />
    );
  }

  return <span aria-hidden="true" className="block h-10 w-10 animate-pulse rounded-md bg-line" />;
}

export function InventoryObjectsTab() {
  const { company, bootstrap } = useAuth();
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);
  const [search, setSearch] = useState('');
  const [branchId, setBranchId] = useState('');
  const [status, setStatus] = useState<AssetStatus | ''>('');
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebouncedValue(search, 300);

  useEffect(() => {
    setPage(1);
  }, [company?.id]);

  const params = {
    search: debouncedSearch || undefined,
    branch: branchId || undefined,
    status: status || undefined,
    active: true,
    page,
  };
  const query = useQuery({
    queryKey: queryKeys.inventoryProducts(company?.id ?? '', params),
    queryFn: () => inventoryApi.listAssets(params),
    enabled: Boolean(company),
  });
  const products = query.data?.results ?? [];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-2">
        <Field
          label="Buscar objeto"
          htmlFor="inventory-object-search"
          className="min-w-[220px]"
        >
          <Input
            id="inventory-object-search"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Nombre, SKU o código de barras"
          />
        </Field>

        <Field label="Sucursal" htmlFor="inventory-object-branch">
          <Select
            id="inventory-object-branch"
            value={branchId}
            onChange={(event) => {
              setBranchId(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Todas</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Estado" htmlFor="inventory-object-status">
          <Select
            id="inventory-object-status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as AssetStatus | '');
              setPage(1);
            }}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      {query.isError ? (
        <ErrorBanner
          message={
            query.error instanceof Error ? query.error.message : 'No se pudo cargar el inventario.'
          }
          onRetry={() => void query.refetch()}
        />
      ) : query.isLoading ? (
        <Skeleton rows={5} />
      ) : products.length === 0 ? (
        <EmptyState
          title="Sin objetos registrados"
          description="Los objetos se crean desde la aplicación móvil y aparecen aquí para consulta."
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="p-3">Objeto</th>
                  <th scope="col" className="p-3">Estado</th>
                  <th scope="col" className="p-3">Sucursal</th>
                  <th scope="col" className="p-3">Responsable</th>
                  <th scope="col" className="p-3">Serie</th>
                  <th scope="col" className="p-3">Garantía</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {products.map((product) => (
                  <tr key={product.id}>
                    <td className="p-3">
                      <div className="flex items-center gap-3">
                        <AssetPhoto product={product} />
                        <div>
                          <p className="font-medium text-ink">{product.name}</p>
                          <p className="text-xs text-muted">{product.sku}</p>
                        </div>
                      </div>
                    </td>
                    <td className="p-3 text-ink">{product.status_display}</td>
                    <td className="p-3 text-ink">{product.branch_name || 'Sin sucursal'}</td>
                    <td className="p-3 text-ink">
                      {product.assigned_worker_name || 'Sin asignar'}
                    </td>
                    <td className="p-3 text-ink">{product.serial_number || '—'}</td>
                    <td className="p-3 text-ink">
                      {product.warranty_until ? formatDateLabel(product.warranty_until) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {query.data ? (
            <Pagination page={page} count={query.data.count} onPage={setPage} />
          ) : null}
        </>
      )}
    </div>
  );
}
