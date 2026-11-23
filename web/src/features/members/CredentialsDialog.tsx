import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';

export function CredentialsDialog({
  open,
  onOpenChange,
  email,
  password,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  email: string;
  password: string;
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Credenciales de acceso"
      description="Entrega esta clave al usuario. No se volverá a mostrar."
      footer={<Button onClick={() => onOpenChange(false)}>Entendido</Button>}
    >
      <dl className="space-y-3 text-sm">
        <div>
          <dt className="text-muted">Correo</dt>
          <dd className="mt-1 font-medium text-ink">{email}</dd>
        </div>
        <div>
          <dt className="text-muted">Clave temporal</dt>
          <dd className="mt-1">
            <code
              data-testid="temporary-password"
              className="rounded bg-surface px-2 py-1 font-mono text-ink"
            >
              {password}
            </code>
          </dd>
        </div>
      </dl>
      <p className="mt-4 text-xs text-muted">
        Al primer ingreso se pedirá cambiarla por una contraseña propia.
      </p>
    </Dialog>
  );
}
