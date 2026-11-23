import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, test, vi } from 'vitest';

import { Badge } from './Badge';
import { Button } from './Button';
import { ConfirmDialog, Dialog } from './Dialog';
import { Field, Input } from './Field';
import { Pagination } from './Pagination';

describe('Button', () => {
  test('se deshabilita y muestra el texto de carga', () => {
    render(
      <Button loading loadingLabel="Entrando…">
        Entrar
      </Button>,
    );
    const button = screen.getByRole('button', { name: 'Entrando…' });
    expect(button).toBeDisabled();
  });
});

describe('Field', () => {
  test('asocia etiqueta, error y campo', () => {
    render(
      <Field label="Correo" htmlFor="email" error="Correo inválido">
        <Input id="email" />
      </Field>,
    );
    expect(screen.getByLabelText('Correo')).toHaveAttribute('id', 'email');
    expect(screen.getByRole('alert')).toHaveTextContent('Correo inválido');
  });
});

describe('Dialog', () => {
  test('cierra con Escape y devuelve el foco', async () => {
    const onOpenChange = vi.fn();
    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            Abrir detalle
          </button>
          <Dialog
            open={open}
            onOpenChange={(next) => {
              setOpen(next);
              onOpenChange(next);
            }}
            title="Detalle de reserva"
          >
            <p>Contenido</p>
          </Dialog>
        </>
      );
    }
    render(<Harness />);
    const trigger = screen.getByRole('button', { name: 'Abrir detalle' });
    await userEvent.click(trigger);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await userEvent.keyboard('{Escape}');

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});

describe('ConfirmDialog', () => {
  test('ejecuta la confirmación', async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open
        onOpenChange={() => {}}
        title="Desactivar cliente"
        description="El cliente dejará de aparecer en el listado activo."
        confirmLabel="Desactivar"
        onConfirm={onConfirm}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Desactivar' }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});

describe('Pagination', () => {
  test('deshabilita anterior en la primera página y siguiente en la última', () => {
    const onPage = vi.fn();
    const { rerender } = render(<Pagination page={1} count={120} onPage={onPage} />);
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeEnabled();

    rerender(<Pagination page={3} count={120} onPage={onPage} />);
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeDisabled();
  });
});

describe('Badge', () => {
  test('muestra el texto y aplica el tono', () => {
    render(<Badge tone="confirmed">Confirmada</Badge>);
    expect(screen.getByText('Confirmada')).toHaveClass('bg-status-confirmed-bg');
  });
});
