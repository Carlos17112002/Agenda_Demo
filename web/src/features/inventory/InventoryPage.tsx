import { useState } from 'react';

import { useAuth } from '../../auth/AuthProvider';
import { EmptyState } from '../../components/ui/EmptyState';
import { PageHeader } from '../../components/ui/PageHeader';
import { InventoryFilesTab } from './InventoryFilesTab';
import { InventoryObjectsTab } from './InventoryObjectsTab';

const TABS = [
  { value: 'objects', label: 'Objetos' },
  { value: 'files', label: 'Archivos' },
] as const;

type TabValue = (typeof TABS)[number]['value'];

export function InventoryPage() {
  const { can } = useAuth();
  const [tab, setTab] = useState<TabValue>('objects');

  if (!can('inventory.read')) {
    return (
      <EmptyState
        title="Sin acceso a inventario"
        description="Tu rol no tiene permiso para consultar objetos ni archivos de la empresa."
      />
    );
  }

  return (
    <section>
      <PageHeader
        title="Inventario"
        description="Objetos y archivos de la empresa. La gestión se realiza desde la aplicación móvil."
      />

      <div role="tablist" aria-label="Inventario" className="mb-4 flex gap-2 border-b border-line">
        {TABS.map((item) => (
          <button
            key={item.value}
            type="button"
            role="tab"
            id={`inventory-tab-${item.value}`}
            aria-selected={tab === item.value}
            aria-controls={`inventory-panel-${item.value}`}
            tabIndex={tab === item.value ? 0 : -1}
            onClick={() => setTab(item.value)}
            onKeyDown={(event) => {
              if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
              event.preventDefault();
              const index = TABS.findIndex((entry) => entry.value === tab);
              const nextIndex =
                event.key === 'ArrowRight'
                  ? (index + 1) % TABS.length
                  : (index - 1 + TABS.length) % TABS.length;
              const next = TABS[nextIndex];
              setTab(next.value);
              window.document.getElementById(`inventory-tab-${next.value}`)?.focus();
            }}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand ${
              tab === item.value
                ? 'border-brand text-ink'
                : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <section
        role="tabpanel"
        id="inventory-panel-objects"
        aria-labelledby="inventory-tab-objects"
        hidden={tab !== 'objects'}
      >
        <InventoryObjectsTab />
      </section>
      <section
        role="tabpanel"
        id="inventory-panel-files"
        aria-labelledby="inventory-tab-files"
        hidden={tab !== 'files'}
      >
        <InventoryFilesTab />
      </section>
    </section>
  );
}
