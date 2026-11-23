import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import type { Service, ServiceListParams } from '../../api/services';
import { servicesApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select } from '../../components/ui/Field';
import { PageHeader } from '../../components/ui/PageHeader';
import { Pagination } from '../../components/ui/Pagination';
import { Skeleton } from '../../components/ui/Skeleton';
import { formatMoney } from '../../lib/format';
import { useDebouncedValue } from '../../lib/useDebouncedValue';
import { ServiceFormDialog } from './ServiceFormDialog';

export function ServicesPage() {
  const { company, bootstrap, can } = useAuth();
  const queryClient = useQueryClient();
  const canWrite = can('catalog.write');

  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);
  const [activeFilter, setActiveFilter] = useState<'' | 'true' | 'false'>('');
  const [branchFilter, setBranchFilter] = useState('');
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Service | null>(null);

  const params: ServiceListParams = {
    search: debouncedSearch || undefined,
    active: activeFilter === '' ? undefined : activeFilter === 'true',
    branch: branchFilter || undefined,
    page,
    ordering: 'name',
  };

  const query = useQuery({
    queryKey: queryKeys.services(company?.id ?? '', params),
    queryFn: () => servicesApi.list(params),
    enabled: Boolean(company),
  });

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(service: Service) {
    setEditing(service);
    setFormOpen(true);
  }

  function branchLabel(service: Service) {
    if (service.branches.length === 0) return 'Todas las sucursales';
    return service.branches
      .map((id) => bootstrap?.branches.find((branch) => branch.id === id)?.name ?? 'Sucursal')
      .join(', ');
  }

  const services = query.data?.results ?? [];

  return (
    <section>
      <PageHeader
        title="Servicios"
        description="Catálogo de servicios, duración, precio y sucursales disponibles."
        actions={canWrite ? <Button onClick={openCreate}>Nuevo servicio</Button> : null}
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_10rem_10rem]">
        <Field label="Buscar" htmlFor="service-search">
          <Input
            id="service-search"
            type="search"
            placeholder="Nombre del servicio"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </Field>
        <Field label="Sucursal" htmlFor="service-branch">
          <Select
            id="service-branch"
            value={branchFilter}
            onChange={(event) => {
              setBranchFilter(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Todas</option>
            {(bootstrap?.branches ?? [])
              .filter((branch) => branch.active)
              .map((branch) => (
                <option key={branch.id} value={branch.id}>
                  {branch.name}
                </option>
              ))}
          </Select>
        </Field>
        <Field label="Estado" htmlFor="service-active">
          <Select
            id="service-active"
            value={activeFilter}
            onChange={(event) => {
              setActiveFilter(event.target.value as '' | 'true' | 'false');
              setPage(1);
            }}
          >
            <option value="">Todos</option>
            <option value="true">Activos</option>
            <option value="false">Inactivos</option>
          </Select>
        </Field>
      </div>

      {query.isError ? (
        <ErrorBanner
          message="No se pudieron cargar los servicios."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {query.isPending ? <Skeleton rows={5} /> : null}

      {query.isSuccess && services.length === 0 ? (
        <EmptyState
          title="Sin servicios"
          description={
            debouncedSearch || activeFilter || branchFilter
              ? 'No hay servicios que coincidan con los filtros.'
              : 'Crea el primer servicio para que la agenda ofrezca cupos.'
          }
          action={canWrite ? <Button onClick={openCreate}>Nuevo servicio</Button> : undefined}
        />
      ) : null}

      {services.length > 0 ? (
        <>
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3">Servicio</th>
                  <th scope="col" className="px-4 py-3">Duración</th>
                  <th scope="col" className="px-4 py-3">Precio</th>
                  <th scope="col" className="px-4 py-3">Sucursales</th>
                  <th scope="col" className="px-4 py-3">Estado</th>
                  <th scope="col" className="px-4 py-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {services.map((service) => (
                  <tr key={service.id}>
                    <td className="px-4 py-3">
                      <span className="block font-medium text-ink">{service.name}</span>
                      {service.description ? (
                        <span className="block text-xs text-muted">{service.description}</span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-muted">{service.duration_minutes} min</td>
                    <td className="px-4 py-3 text-muted">{formatMoney(service.price)}</td>
                    <td className="px-4 py-3 text-muted">{branchLabel(service)}</td>
                    <td className="px-4 py-3">
                      <Badge tone={service.active ? 'active' : 'inactive'}>
                        {service.active ? 'Activo' : 'Inactivo'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {canWrite ? (
                        <Button variant="ghost" onClick={() => openEdit(service)}>
                          Editar
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} count={query.data?.count ?? 0} onPage={setPage} />
        </>
      ) : null}

      {formOpen ? (
        <ServiceFormDialog
          open
          service={editing}
          onOpenChange={(next) => {
            if (!next) setFormOpen(false);
          }}
          onSaved={() => {
            void queryClient.invalidateQueries({ queryKey: ['services', company?.id ?? ''] });
          }}
        />
      ) : null}
    </section>
  );
}
