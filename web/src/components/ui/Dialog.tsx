import * as RadixDialog from '@radix-ui/react-dialog';
import { useEffect, useRef, type ReactNode } from 'react';

import { Button } from './Button';

type DialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  footer?: ReactNode;
  wide?: boolean;
  children: ReactNode;
};

export function Dialog({ open, onOpenChange, title, description, footer, wide, children }: DialogProps) {
  const restoreFocus = useRef<HTMLElement | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const wasOpen = useRef(open);

  useEffect(() => {
    const track = () => {
      const active = document.activeElement;
      if (!(active instanceof HTMLElement)) return;
      if (contentRef.current?.contains(active)) return;
      restoreFocus.current = active;
    };
    track();
    document.addEventListener('focusin', track);
    return () => document.removeEventListener('focusin', track);
  }, []);

  useEffect(() => {
    if (wasOpen.current && !open) restoreFocus.current?.focus();
    wasOpen.current = open;
  }, [open]);

  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <RadixDialog.Content
          ref={contentRef}
          className={`fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[92vw] ${wide ? 'max-w-4xl' : 'max-w-lg'} -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg bg-panel p-6 shadow-xl focus:outline-none`}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <RadixDialog.Title className="text-lg font-semibold text-ink">{title}</RadixDialog.Title>
              {description ? (
                <RadixDialog.Description className="mt-1 text-sm text-muted">
                  {description}
                </RadixDialog.Description>
              ) : null}
            </div>
            <RadixDialog.Close aria-label="Cerrar" className="rounded p-1 text-muted hover:bg-surface">
              <span aria-hidden="true">×</span>
            </RadixDialog.Close>
          </div>
          <div className="mt-4">{children}</div>
          {footer ? <div className="mt-6 flex justify-end gap-2">{footer}</div> : null}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

type ConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  loading?: boolean;
  danger?: boolean;
};

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onConfirm,
  loading = false,
  danger = true,
}: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Volver
          </Button>
          <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-sm text-muted">Esta acción quedará registrada en la auditoría.</p>
    </Dialog>
  );
}
