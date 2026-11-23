import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import type { InventoryDocument } from '../../api/inventory';
import { queryKeys } from '../../api/queryKeys';
import { inventoryApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select } from '../../components/ui/Field';
import { Pagination } from '../../components/ui/Pagination';
import { Skeleton } from '../../components/ui/Skeleton';
import { useDebouncedValue } from '../../lib/useDebouncedValue';

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  const units = ['KB', 'MB', 'GB'];
  let size = value / 1024;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  const formatted = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 1 }).format(size);
  return `${formatted} ${units[unit]}`;
}

export function InventoryFilesTab() {
  const { company } = useAuth();
  const [search, setSearch] = useState('');
  const [linked, setLinked] = useState<'' | 'true' | 'false'>('');
  const [page, setPage] = useState(1);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const debouncedSearch = useDebouncedValue(search, 300);

  useEffect(() => {
    setPage(1);
  }, [company?.id]);

  const params = {
    search: debouncedSearch || undefined,
    linked: linked === '' ? undefined : linked === 'true',
    page,
  };
  const query = useQuery({
    queryKey: queryKeys.inventoryDocuments(company?.id ?? '', params),
    queryFn: () => inventoryApi.listDocuments(params),
    enabled: Boolean(company),
  });
  const documents = query.data?.results ?? [];

  async function download(file: InventoryDocument) {
    setDownloading(file.id);
    setDownloadError(null);
    try {
      const result = await inventoryApi.downloadDocument(file);
      const objectUrl = URL.createObjectURL(result.blob);
      const anchor = window.document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = result.filename ?? file.original_name;
      window.document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
    } catch (error) {
      setDownloadError(
        error instanceof Error ? error.message : 'No se pudo descargar el archivo.',
      );
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-2">
        <Field label="Buscar archivo" htmlFor="inventory-file-search" className="min-w-[220px]">
          <Input
            id="inventory-file-search"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Nombre o nombre original"
          />
        </Field>

        <Field label="Vínculo" htmlFor="inventory-file-linked">
          <Select
            id="inventory-file-linked"
            value={linked}
            onChange={(event) => {
              setLinked(event.target.value as '' | 'true' | 'false');
              setPage(1);
            }}
          >
            <option value="">Todos</option>
            <option value="true">Vinculados a un objeto</option>
            <option value="false">Sin vínculo</option>
          </Select>
        </Field>
      </div>

      {downloadError ? <ErrorBanner message={downloadError} /> : null}

      {query.isError ? (
        <ErrorBanner
          message={
            query.error instanceof Error ? query.error.message : 'No se pudieron cargar los archivos.'
          }
          onRetry={() => void query.refetch()}
        />
      ) : query.isLoading ? (
        <Skeleton rows={5} />
      ) : documents.length === 0 ? (
        <EmptyState
          title="Sin archivos"
          description="Los archivos se suben desde la aplicación móvil. Aquí puedes consultarlos y descargarlos."
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="p-3">Archivo</th>
                  <th scope="col" className="p-3">Vínculo</th>
                  <th scope="col" className="p-3">Tamaño</th>
                  <th scope="col" className="p-3">Subido por</th>
                  <th scope="col" className="p-3">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {documents.map((file) => (
                  <tr key={file.id}>
                    <td className="p-3">
                      <p className="font-medium text-ink">{file.name}</p>
                      <p className="text-xs text-muted">{file.original_name}</p>
                    </td>
                    <td className="p-3 text-ink">
                      {file.product_name ?? 'Sin vínculo'}
                      {file.product_sku ? (
                        <span className="block text-xs text-muted">{file.product_sku}</span>
                      ) : null}
                    </td>
                    <td className="p-3 text-ink">{formatBytes(file.size)}</td>
                    <td className="p-3 text-ink">{file.uploaded_by_email ?? '—'}</td>
                    <td className="p-3">
                      <button
                        type="button"
                        aria-label={`Descargar ${file.name}`}
                        disabled={downloading === file.id}
                        onClick={() => void download(file)}
                        className="rounded-md border border-line bg-panel px-3 py-1.5 text-sm font-medium text-ink transition hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {downloading === file.id ? 'Descargando…' : 'Descargar'}
                      </button>
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
