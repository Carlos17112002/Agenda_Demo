import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import type { CashSummary, SalesSummary } from '../../api/summary';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { SummaryPage } from './SummaryPage';

const salesSummary: SalesSummary = {
  range: {
    date_from: '2026-11-05',
    date_to: '2026-11-11',
    timezone: 'America/Santiago',
    branch: null,
  },
  totals: {
    sales: 2,
    subtotal: '105000',
    discounts: '5000',
    total: '100000',
    paid: '100000',
    cost: '40000',
    profit: '60000',
    margin_percent: '60.00',
    average_ticket: '50000',
  },
  by_payment_method: [
    { method: 'cash', method_display: 'Efectivo', count: 1, amount: '60000' },
  ],
  by_day: [
    {
      date: '2026-11-11',
      sales: 2,
      subtotal: '105000',
      discounts: '5000',
      total: '100000',
      cost: '40000',
      profit: '60000',
    },
  ],
  by_branch: [
    {
      branch: 'branch-1',
      branch_name: 'Providencia',
      sales: 2,
      subtotal: '105000',
      discounts: '5000',
      total: '100000',
      cost: '40000',
    },
  ],
  top_products: [
    {
      product: 'product-1',
      description: 'Shampoo',
      sku: 'SH-01',
      quantity: '1.000',
      total: '10000',
      cost: '4000',
      profit: '6000',
    },
  ],
  top_services: [
    {
      service: 'service-1',
      description: 'Corte de cabello',
      sku: null,
      quantity: '2.000',
      total: '100000',
      cost: '40000',
      profit: '60000',
    },
  ],
};

const cashSummary: CashSummary = {
  range: {
    date_from: '2026-11-05',
    date_to: '2026-11-11',
    timezone: 'America/Santiago',
    branch: null,
  },
  totals: {
    sessions: 1,
    open: 0,
    closed: 1,
    opening: '20000',
    cash_sales: '60000',
    cash_expenses: '5000',
    expected: '75000',
    closing: '75000',
    difference: '0',
    expenses: '5000',
  },
  sessions: [
    {
      id: 'session-1',
      number: 'CJ-001',
      branch: 'branch-1',
      branch_name: 'Providencia',
      status: 'closed',
      opened_at: '2026-11-11T12:00:00Z',
      closed_at: '2026-11-11T21:00:00Z',
      opening_amount: '20000',
      cash_sales: '60000',
      cash_expenses: '5000',
      expected: '75000',
      closing_amount: '75000',
      difference: '0',
    },
  ],
  expenses_by_category: [{ category: 'Insumos', total: '5000' }],
  expenses_by_method: [{ method: 'cash', method_display: 'Efectivo', total: '5000' }],
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={makeAuthValue()}>
      <QueryClientProvider client={queryClient}>
        <SummaryPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

function summaryHandlers(urls: { sales: string[]; cash: string[] }) {
  return [
    http.get('http://api.test/api/v1/reports/sales-summary/', ({ request }) => {
      urls.sales.push(request.url);
      return HttpResponse.json(salesSummary);
    }),
    http.get('http://api.test/api/v1/reports/cash-summary/', ({ request }) => {
      urls.cash.push(request.url);
      return HttpResponse.json(cashSummary);
    }),
  ];
}

describe('SummaryPage', () => {
  test('muestra totales de ventas del rango por defecto', async () => {
    const urls = { sales: [] as string[], cash: [] as string[] };
    server.use(...summaryHandlers(urls));
    renderPage();

    expect(await screen.findByText('Corte de cabello')).toBeInTheDocument();
    expect(screen.getAllByText('$ 100.000').length).toBeGreaterThan(0);
    expect(screen.getAllByText('$ 60.000').length).toBeGreaterThan(0);
    expect(screen.getByText('60 %')).toBeInTheDocument();
    expect(screen.getAllByText('Efectivo').length).toBeGreaterThan(0);
    expect(screen.getByText('Shampoo')).toBeInTheDocument();
    expect(screen.getAllByText('Providencia').length).toBeGreaterThan(1);

    expect(urls.sales).toHaveLength(1);
    expect(urls.sales[0]).toContain('date_from=');
    expect(urls.sales[0]).toContain('date_to=');
    expect(urls.sales[0]).not.toContain('branch=');
  });

  test('filtra por sucursal', async () => {
    const urls = { sales: [] as string[], cash: [] as string[] };
    server.use(...summaryHandlers(urls));
    renderPage();

    await screen.findByText('Corte de cabello');
    await userEvent.selectOptions(screen.getByLabelText('Sucursal'), 'branch-1');

    await waitFor(() => expect(urls.sales.length).toBe(2));
    expect(urls.sales[1]).toContain('branch=branch-1');
    expect(urls.cash[1]).toContain('branch=branch-1');
  });

  test('muestra caja, sesiones y gastos por categoría', async () => {
    const urls = { sales: [] as string[], cash: [] as string[] };
    server.use(...summaryHandlers(urls));
    renderPage();

    expect(await screen.findByText('CJ-001')).toBeInTheDocument();
    expect(screen.getByText('Cerrada')).toBeInTheDocument();
    expect(screen.getByText('Insumos')).toBeInTheDocument();
    expect(screen.getAllByText('$ 75.000').length).toBeGreaterThan(0);
    expect(urls.cash).toHaveLength(1);
  });
});
