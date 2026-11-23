import type { ApiClient } from './client';
import type { Paginated, UUID } from './types';

export type AssetStatus = 'available' | 'assigned' | 'maintenance' | 'retired';

export type InventoryProduct = {
  id: UUID;
  company: UUID;
  kind: 'asset';
  kind_display: string;
  status: AssetStatus;
  status_display: string;
  sku: string;
  name: string;
  description: string;
  category: UUID | null;
  category_name: string | null;
  unit: string;
  unit_display: string;
  cost: string;
  price: string;
  reorder_point: string;
  barcode: string;
  branch: UUID | null;
  branch_name: string | null;
  assigned_worker: UUID | null;
  assigned_worker_name: string;
  serial_number: string;
  internal_code: string;
  quantity: number;
  purchase_date: string | null;
  supplier: UUID | null;
  supplier_name: string | null;
  warranty_until: string | null;
  notes: string;
  photo_url: string;
  photo_content_type: string;
  photo_size: number;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type InventoryDocument = {
  id: UUID;
  company: UUID;
  client_id: UUID | null;
  name: string;
  original_name: string;
  content_type: string;
  size: number;
  product: UUID | null;
  product_name: string | null;
  product_sku: string | null;
  uploaded_by_email: string | null;
  download_url: string;
  created_at: string;
  updated_at: string;
};

export type AssetListParams = {
  search?: string;
  branch?: UUID;
  status?: AssetStatus;
  active?: boolean;
  page?: number;
};

export type DocumentListParams = {
  search?: string;
  linked?: boolean;
  product?: UUID;
  page?: number;
};

export function createInventoryApi(client: ApiClient) {
  return {
    listAssets: (params: AssetListParams = {}) =>
      client.get<Paginated<InventoryProduct>>('/api/v1/inventory/products/', {
        ...params,
        kind: 'asset',
      }),
    listDocuments: (params: DocumentListParams = {}) =>
      client.get<Paginated<InventoryDocument>>('/api/v1/inventory/documents/', {
        ...params,
      }),
    downloadDocument: (file: Pick<InventoryDocument, 'download_url'>) =>
      client.download(file.download_url),
    productPhoto: (path: string) => client.download(path),
  };
}

export type InventoryApi = ReturnType<typeof createInventoryApi>;
