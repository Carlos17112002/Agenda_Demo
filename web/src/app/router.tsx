import { createBrowserRouter, type RouteObject } from 'react-router-dom';

import { CompanyChooserPage } from '../features/companies/CompanyChooserPage';
import { LoginPage } from '../features/auth/LoginPage';
import { ChangePasswordPage } from '../features/auth/ChangePasswordPage';
import { AgendaPage } from '../features/agenda/AgendaPage';
import { BrandingPage } from '../features/branding/BrandingPage';
import { CustomersPage } from '../features/customers/CustomersPage';
import { InventoryPage } from '../features/inventory/InventoryPage';
import { MembersPage } from '../features/members/MembersPage';
import { ServicesPage } from '../features/services/ServicesPage';
import { SummaryPage } from '../features/summary/SummaryPage';
import { TeamPage } from '../features/team/TeamPage';
import { AppLayout } from './AppLayout';
import {
  AccessDeniedPage,
  ForcePasswordChange,
  NotFoundPage,
  RequireAuthenticated,
  RequirePermission,
  RequireReady,
} from './guards';
import { HomeRedirect } from './HomeRedirect';

export const routeObjects: RouteObject[] = [
  { path: '/login', element: <LoginPage /> },
  {
    path: '/empresa',
    element: (
      <RequireAuthenticated>
        <CompanyChooserPage />
      </RequireAuthenticated>
    ),
  },
  {
    path: '/cambiar-clave',
    element: (
      <RequireAuthenticated>
        <RequireReady>
          <ChangePasswordPage />
        </RequireReady>
      </RequireAuthenticated>
    ),
  },
  {
    path: '/',
    element: (
      <RequireAuthenticated>
        <RequireReady>
          <ForcePasswordChange>
            <AppLayout />
          </ForcePasswordChange>
        </RequireReady>
      </RequireAuthenticated>
    ),
    children: [
      { index: true, element: <HomeRedirect /> },
      {
        path: 'agenda',
        element: (
          <RequirePermission permission="bookings.read">
            <AgendaPage />
          </RequirePermission>
        ),
      },
      {
        path: 'clientes',
        element: (
          <RequirePermission permission="customers.read">
            <CustomersPage />
          </RequirePermission>
        ),
      },
      {
        path: 'servicios',
        element: (
          <RequirePermission permission="catalog.read">
            <ServicesPage />
          </RequirePermission>
        ),
      },
      {
        path: 'equipo',
        element: (
          <RequirePermission permission="workforce.read">
            <TeamPage />
          </RequirePermission>
        ),
      },
      {
        path: 'inventario',
        element: (
          <RequirePermission permission="inventory.read">
            <InventoryPage />
          </RequirePermission>
        ),
      },
      {
        path: 'resumen',
        element: (
          <RequirePermission permission="reports.read">
            <SummaryPage />
          </RequirePermission>
        ),
      },
      {
        path: 'usuarios',
        element: (
          <RequirePermission permission="company.manage">
            <MembersPage />
          </RequirePermission>
        ),
      },
      {
        path: 'marca',
        element: (
          <RequirePermission permission="company.manage">
            <BrandingPage />
          </RequirePermission>
        ),
      },
      { path: 'sin-acceso', element: <AccessDeniedPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routeObjects);
