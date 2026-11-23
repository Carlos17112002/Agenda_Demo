import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { queryKeys } from '../../api/queryKeys';
import { summaryApi } from '../../api/runtime';
import type { SummaryParams } from '../../api/summary';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select } from '../../components/ui/Field';
import { PageHeader } from '../../components/ui/PageHeader';
import { Skeleton } from '../../components/ui/Skeleton';
import { formatDateLabel, shiftDate, todayInZone } from '../../lib/dates';
import { formatMoney, formatPercent } from '../../lib/format';

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-panel p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold text-ink">{value}</p>
    </div>
  );
}

export function SummaryPage() {
  const { company, bootstrap } = useAuth();
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);
  const [branchId, setBranchId] = useState('');
  const timezone =
    branches.find((branch) => branch.id === branchId)?.timezone
    ?? branches[0]?.timezone
    ?? 'America/Santiago';
  const [dateTo, setDateTo] = useState(() => todayInZone(timezone));
  const [dateFrom, setDateFrom] = useState(() => shiftDate(todayInZone(timezone), -6));

  const rangeValid = Boolean(dateFrom && dateTo && dateFrom <= dateTo);
  const params: SummaryParams = {
    date_from: dateFrom,
    date_to: dateTo,
    branch: branchId || undefined,
  };

  const salesQuery = useQuery({
    queryKey: queryKeys.salesSummary(company?.id ?? '', params),
    queryFn: () => summaryApi.sales(params),
    enabled: Boolean(company) && rangeValid,
  });
  const cashQuery = useQuery({
    queryKey: queryKeys.cashSummary(company?.id ?? '', params),
    queryFn: () => summaryApi.cash(params),
    enabled: Boolean(company) && rangeValid,
  });

  const sales = salesQuery.data;
  const cash = cashQuery.data;

  return (
    <section>
      <PageHeader
        title="Resumen"
        description="Ventas y caja de la empresa para el rango y la sucursal seleccionados."
      />

      <div className="mb-6 grid gap-3 sm:grid-cols-3">
        <Field label="Desde" htmlFor="summary-from">
          <Input
            id="summary-from"
            type="date"
            max={dateTo}
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
          />
        </Field>
        <Field label="Hasta" htmlFor="summary-to">
          <Input
            id="summary-to"
            type="date"
            min={dateFrom}
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
          />
        </Field>
        <Field label="Sucursal" htmlFor="summary-branch">
          <Select
            id="summary-branch"
            value={branchId}
            onChange={(event) => setBranchId(event.target.value)}
          >
            <option value="">Todas las sucursales</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      {!rangeValid ? (
        <ErrorBanner message="La fecha desde no puede ser posterior a la fecha hasta." />
      ) : null}

      <section aria-labelledby="summary-sales-heading" className="mb-8">
        <h2 id="summary-sales-heading" className="mb-3 text-lg font-semibold text-ink">
          Ventas
        </h2>

        {salesQuery.isError ? (
          <ErrorBanner
            message="No se pudo cargar el resumen de ventas."
            onRetry={() => void salesQuery.refetch()}
          />
        ) : null}
        {salesQuery.isPending && rangeValid ? <Skeleton rows={3} /> : null}

        {sales ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <Metric label="Total vendido" value={formatMoney(sales.totals.total)} />
              <Metric label="Pagado" value={formatMoney(sales.totals.paid)} />
              <Metric label="Ganancia" value={formatMoney(sales.totals.profit)} />
              <Metric label="Margen" value={formatPercent(sales.totals.margin_percent)} />
              <Metric label="Ticket promedio" value={formatMoney(sales.totals.average_ticket)} />
              <Metric label="Reservas" value={String(sales.totals.sales)} />
            </div>

            <div className="mt-5 grid gap-5 lg:grid-cols-2">
              <div className="rounded-lg border border-line bg-panel">
                <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                  Ventas por día
                </h3>
                {sales.by_day.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-muted">Sin ventas en el rango.</p>
                ) : (
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs uppercase tracking-wide text-muted">
                      <tr>
                        <th scope="col" className="px-4 py-2">
                          Día
                        </th>
                        <th scope="col" className="px-4 py-2">
                          Reservas
                        </th>
                        <th scope="col" className="px-4 py-2 text-right">
                          Total
                        </th>
                        <th scope="col" className="px-4 py-2 text-right">
                          Ganancia
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {sales.by_day.map((day) => (
                        <tr key={day.date}>
                          <td className="px-4 py-2 text-ink">{formatDateLabel(day.date)}</td>
                          <td className="px-4 py-2 text-muted">{day.sales}</td>
                          <td className="px-4 py-2 text-right text-muted">
                            {formatMoney(day.total)}
                          </td>
                          <td className="px-4 py-2 text-right text-muted">
                            {formatMoney(day.profit)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="rounded-lg border border-line bg-panel">
                <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                  Por método de pago
                </h3>
                {sales.by_payment_method.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-muted">Sin pagos en el rango.</p>
                ) : (
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs uppercase tracking-wide text-muted">
                      <tr>
                        <th scope="col" className="px-4 py-2">
                          Método
                        </th>
                        <th scope="col" className="px-4 py-2">
                          Cantidad
                        </th>
                        <th scope="col" className="px-4 py-2 text-right">
                          Monto
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {sales.by_payment_method.map((row) => (
                        <tr key={row.method}>
                          <td className="px-4 py-2 text-ink">{row.method_display}</td>
                          <td className="px-4 py-2 text-muted">{row.count}</td>
                          <td className="px-4 py-2 text-right text-muted">
                            {formatMoney(row.amount)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            <div className="mt-5 grid gap-5 lg:grid-cols-2">
              <div className="rounded-lg border border-line bg-panel">
                <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                  Ventas por sucursal
                </h3>
                {sales.by_branch.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-muted">Sin ventas por sucursal en el rango.</p>
                ) : (
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs uppercase tracking-wide text-muted">
                      <tr>
                        <th scope="col" className="px-4 py-2">
                          Sucursal
                        </th>
                        <th scope="col" className="px-4 py-2">
                          Reservas
                        </th>
                        <th scope="col" className="px-4 py-2 text-right">
                          Total
                        </th>
                        <th scope="col" className="px-4 py-2 text-right">
                          Costo
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {sales.by_branch.map((row) => (
                        <tr key={row.branch}>
                          <td className="px-4 py-2 text-ink">{row.branch_name}</td>
                          <td className="px-4 py-2 text-muted">{row.sales}</td>
                          <td className="px-4 py-2 text-right text-muted">
                            {formatMoney(row.total)}
                          </td>
                          <td className="px-4 py-2 text-right text-muted">
                            {formatMoney(row.cost)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="rounded-lg border border-line bg-panel">
                <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                  Productos más vendidos
                </h3>
                {sales.top_products.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-muted">Sin productos vendidos en el rango.</p>
                ) : (
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs uppercase tracking-wide text-muted">
                      <tr>
                        <th scope="col" className="px-4 py-2">
                          Producto
                        </th>
                        <th scope="col" className="px-4 py-2">
                          SKU
                        </th>
                        <th scope="col" className="px-4 py-2">
                          Cantidad
                        </th>
                        <th scope="col" className="px-4 py-2 text-right">
                          Total
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {sales.top_products.map((item) => (
                        <tr key={item.product ?? item.description}>
                          <td className="px-4 py-2 text-ink">{item.description}</td>
                          <td className="px-4 py-2 text-muted">{item.sku ?? '—'}</td>
                          <td className="px-4 py-2 text-muted">{item.quantity}</td>
                          <td className="px-4 py-2 text-right text-muted">
                            {formatMoney(item.total)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            <div className="mt-5 rounded-lg border border-line bg-panel">
              <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                Servicios más vendidos
              </h3>
              {sales.top_services.length === 0 ? (
                <p className="px-4 py-6 text-sm text-muted">Sin servicios vendidos en el rango.</p>
              ) : (
                <table className="w-full text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-muted">
                    <tr>
                      <th scope="col" className="px-4 py-2">
                        Servicio
                      </th>
                      <th scope="col" className="px-4 py-2">
                        Cantidad
                      </th>
                      <th scope="col" className="px-4 py-2 text-right">
                        Total
                      </th>
                      <th scope="col" className="px-4 py-2 text-right">
                        Ganancia
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {sales.top_services.map((item) => (
                      <tr key={item.service ?? item.description}>
                        <td className="px-4 py-2 text-ink">{item.description}</td>
                        <td className="px-4 py-2 text-muted">{item.quantity}</td>
                        <td className="px-4 py-2 text-right text-muted">
                          {formatMoney(item.total)}
                        </td>
                        <td className="px-4 py-2 text-right text-muted">
                          {formatMoney(item.profit)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        ) : null}
      </section>

      <section aria-labelledby="summary-cash-heading">
        <h2 id="summary-cash-heading" className="mb-3 text-lg font-semibold text-ink">
          Caja
        </h2>

        {cashQuery.isError ? (
          <ErrorBanner
            message="No se pudo cargar el resumen de caja."
            onRetry={() => void cashQuery.refetch()}
          />
        ) : null}
        {cashQuery.isPending && rangeValid ? <Skeleton rows={3} /> : null}

        {cash ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <Metric label="Sesiones" value={String(cash.totals.sessions)} />
              <Metric label="Esperado" value={formatMoney(cash.totals.expected)} />
              <Metric label="Contado" value={formatMoney(cash.totals.closing)} />
              <Metric label="Diferencia" value={formatMoney(cash.totals.difference)} />
              <Metric label="Gastos" value={formatMoney(cash.totals.expenses)} />
            </div>

            <div className="mt-5 overflow-x-auto rounded-lg border border-line bg-panel">
              <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                Sesiones de caja
              </h3>
              {cash.sessions.length === 0 ? (
                <p className="px-4 py-6 text-sm text-muted">Sin sesiones en el rango.</p>
              ) : (
                <table className="w-full text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-muted">
                    <tr>
                      <th scope="col" className="px-4 py-2">
                        Número
                      </th>
                      <th scope="col" className="px-4 py-2">
                        Sucursal
                      </th>
                      <th scope="col" className="px-4 py-2">
                        Estado
                      </th>
                      <th scope="col" className="px-4 py-2 text-right">
                        Apertura
                      </th>
                      <th scope="col" className="px-4 py-2 text-right">
                        Esperado
                      </th>
                      <th scope="col" className="px-4 py-2 text-right">
                        Cierre
                      </th>
                      <th scope="col" className="px-4 py-2 text-right">
                        Diferencia
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {cash.sessions.map((session) => (
                      <tr key={session.id}>
                        <td className="px-4 py-2 font-medium text-ink">{session.number}</td>
                        <td className="px-4 py-2 text-muted">{session.branch_name}</td>
                        <td className="px-4 py-2">
                          <Badge tone={session.status === 'open' ? 'active' : 'inactive'}>
                            {session.status === 'open' ? 'Abierta' : 'Cerrada'}
                          </Badge>
                        </td>
                        <td className="px-4 py-2 text-right text-muted">
                          {formatMoney(session.opening_amount)}
                        </td>
                        <td className="px-4 py-2 text-right text-muted">
                          {formatMoney(session.expected)}
                        </td>
                        <td className="px-4 py-2 text-right text-muted">
                          {formatMoney(session.closing_amount)}
                        </td>
                        <td className="px-4 py-2 text-right text-muted">
                          {session.difference === null ? '—' : formatMoney(session.difference)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="mt-5 rounded-lg border border-line bg-panel">
              <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                Gastos por categoría
              </h3>
              {cash.expenses_by_category.length === 0 ? (
                <p className="px-4 py-6 text-sm text-muted">Sin gastos en el rango.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {cash.expenses_by_category.map((row) => (
                    <li key={row.category} className="flex justify-between px-4 py-2 text-sm">
                      <span className="text-ink">{row.category}</span>
                      <span className="text-muted">{formatMoney(row.total)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="mt-5 rounded-lg border border-line bg-panel">
              <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
                Gastos por método
              </h3>
              {cash.expenses_by_method.length === 0 ? (
                <p className="px-4 py-6 text-sm text-muted">Sin gastos por método en el rango.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {cash.expenses_by_method.map((row) => (
                    <li key={row.method} className="flex justify-between px-4 py-2 text-sm">
                      <span className="text-ink">{row.method_display}</span>
                      <span className="text-muted">{formatMoney(row.total)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        ) : null}
      </section>

      {sales && cash && sales.totals.sales === 0 && cash.totals.sessions === 0 ? (
        <EmptyState
          title="Sin movimientos"
          description="No hay ventas ni sesiones de caja en el rango seleccionado."
        />
      ) : null}
    </section>
  );
}
