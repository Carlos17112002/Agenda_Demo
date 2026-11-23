import type { SaasCompanyCreateResult } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';

export function SaasCompanyCreatedDialog({
  open,
  result,
  onOpenChange,
}: {
  open: boolean;
  result: SaasCompanyCreateResult | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Empresa creada"
      description="Entrega estas credenciales al propietario. La clave no se volverá a mostrar."
      footer={<Button onClick={() => onOpenChange(false)}>Entendido</Button>}
    >
      <dl className="space-y-3 text-sm">
        <div>
          <dt className="text-muted">Empresa</dt>
          <dd className="mt-1 font-medium text-ink">{result?.company_name}</dd>
        </div>
        <div>
          <dt className="text-muted">Correo del propietario</dt>
          <dd className="mt-1 font-medium text-ink">{result?.owner_email}</dd>
        </div>
        <div>
          <dt className="text-muted">Clave temporal</dt>
          <dd className="mt-1">
            <code
              data-testid="temporary-password"
              className="rounded bg-surface px-2 py-1 font-mono text-ink"
            >
              {result?.temporary_password}
            </code>
          </dd>
        </div>
        <div>
          <dt className="text-muted">Enlace de reservas</dt>
          <dd className="mt-1">
            <code className="break-all rounded bg-surface px-2 py-1 font-mono text-ink">
              {result?.booking_url}
            </code>
          </dd>
        </div>
      </dl>
      <p className="mt-4 text-xs text-muted">
        Al primer ingreso se pedirá cambiar la clave por una propia.
      </p>
    </Dialog>
  );
}
