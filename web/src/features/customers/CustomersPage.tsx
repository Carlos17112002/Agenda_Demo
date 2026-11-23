import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError } from '../../api/client';
import type { Customer, CustomerListParams } from '../../api/customers';
import { customersApi } from '../../api/runtime';
import { queryKeys } from '../../api/queryKeys';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/Dialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select } from '../../components/ui/Field';
import { PageHeader } from '../../components/ui/PageHeader';
import { Pagination } from '../../components/ui/Pagination';
import { Skeleton } from '../../components/ui/Skeleton';
import { useDebouncedValue } from '../../lib/useDebouncedValue';
import { CustomerFormDialog } from './CustomerFormDialog';
import { CustomerHistoryDialog } from './CustomerHistoryDialog';

export function CustomersPage() {
  const { company, can } = useAuth();
  const queryClient = useQueryClient();
  const canWrite = can('customers.write');

  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);
  const [activeFilter, setActiveFilter] = useState<'' | 'true' | 'false'>('');
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [history, setHistory] = useState<Customer | null>(null);
  const [pendingToggle, setPendingToggle] = useState<Customer | null>(null);

  const params: CustomerListParams = {
    search: debouncedSearch || undefined,
    active: activeFilter === '' ? undefined : activeFilter === 'true',
    page,
    ordering: 'last_name',
  };

  const query = useQuery({
    queryKey: queryKeys.customers(company?.id ?? '', params),
    queryFn: () => customersApi.list(params),
    enabled: Boolean(company),
  });

  const toggle = useMutation({
    mutationFn: (customer: Customer) => customersApi.setActive(customer.id, !customer.active),
    onSuccess: () => {
      setPendingToggle(null);
      void queryClient.invalidateQueries({ queryKey: ['customers', company?.id ?? ''] });
    },
  });

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(customer: Customer) {
    setEditing(customer);
    setFormOpen(true);
  }

  const customers = query.data?.results ?? [];
  const toggleError =
    toggle.error instanceof ApiError
      ? toggle.error.message
      : toggle.error
        ? 'No se pudo actualizar el cliente.'
        : null;

  return (
    <section>
      <PageHeader
        title="Clientes"
        description="Directorio de clientes de la empresa con su historial de reservas."
        actions={canWrite ? <Button onClick={openCreate}>Nuevo cliente</Button> : null}
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_12rem]">
        <Field label="Buscar" htmlFor="customer-search">
          <Input
            id="customer-search"
            type="search"
            placeholder="Nombre, correo, teléfono o documento"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </Field>
        <Field label="Estado" htmlFor="customer-active">
          <Select
            id="customer-active"
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

      {toggleError ? <ErrorBanner message={toggleError} /> : null}
      {query.isError ? (
        <ErrorBanner message="No se pudieron cargar los clientes." onRetry={() => void query.refetch()} />
      ) : null}
      {query.isPending ? <Skeleton rows={5} /> : null}

      {query.isSuccess && customers.length === 0 ? (
        <EmptyState
          title="Sin clientes"
          description={
            debouncedSearch || activeFilter
              ? 'No hay clientes que coincidan con los filtros.'
              : 'Crea el primer cliente para asociarlo a reservas.'
          }
          action={canWrite ? <Button onClick={openCreate}>Nuevo cliente</Button> : undefined}
        />
      ) : null}

      {customers.length > 0 ? (
        <>
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="whitespace-nowrap px-4 py-3">
                    Cliente
                  </th>
                  <th scope="col" className="whitespace-nowrap px-4 py-3">
                    Contacto
                  </th>
                  <th scope="col" className="whitespace-nowrap px-4 py-3">
                    Documento
                  </th>
                  <th scope="col" className="whitespace-nowrap px-4 py-3">
                    Estado
                  </th>
                  <th scope="col" className="whitespace-nowrap px-4 py-3 text-right">
                    Acciones
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {customers.map((customer) => (
                  <tr key={customer.id}>
                    <td className="whitespace-nowrap px-4 py-3 font-medium text-ink">{customer.display_name}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-muted">
                      <span className="block">{customer.email || 'Sin correo'}</span>
                      <span className="block text-xs">{customer.phone || 'Sin teléfono'}</span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-muted">{customer.document_id || '—'}</td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <Badge tone={customer.active ? 'active' : 'inactive'}>
                        {customer.active ? 'Activo' : 'Inactivo'}
                      </Badge>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <div className="flex justify-end gap-1">
                        {can('bookings.read') ? (
                          <Button variant="ghost" onClick={() => setHistory(customer)}>
                            Historial
                          </Button>
                        ) : null}
                        {canWrite ? (
                          <>
                            <Button variant="ghost" onClick={() => openEdit(customer)}>
                              Editar
                            </Button>
                            <Button variant="ghost" onClick={() => setPendingToggle(customer)}>
                              {customer.active ? 'Desactivar' : 'Reactivar'}
                            </Button>
                          </>
                        ) : null}
                      </div>
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
        <CustomerFormDialog
          open
          customer={editing}
          onOpenChange={(next) => {
            if (!next) setFormOpen(false);
          }}
          onSaved={() => {
            void queryClient.invalidateQueries({ queryKey: ['customers', company?.id ?? ''] });
          }}
        />
      ) : null}

      <CustomerHistoryDialog customer={history} onClose={() => setHistory(null)} />

      <ConfirmDialog
        open={Boolean(pendingToggle)}
        onOpenChange={(next) => {
          if (!next) setPendingToggle(null);
        }}
        title={pendingToggle?.active ? 'Desactivar cliente' : 'Reactivar cliente'}
        description={
          pendingToggle
            ? `${pendingToggle.active ? 'El cliente dejará de aparecer' : 'El cliente volverá a aparecer'} en las búsquedas y nuevas reservas. Su historial se conserva.`
            : ''
        }
        confirmLabel={pendingToggle?.active ? 'Desactivar' : 'Reactivar'}
        danger={Boolean(pendingToggle?.active)}
        loading={toggle.isPending}
        onConfirm={() => {
          if (pendingToggle) toggle.mutate(pendingToggle);
        }}
      />
    </section>
  );
}
