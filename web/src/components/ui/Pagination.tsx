import { Button } from './Button';

export function Pagination({
  page,
  count,
  pageSize = 50,
  onPage,
}: {
  page: number;
  count: number;
  pageSize?: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  const from = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, count);

  return (
    <nav aria-label="Paginación" className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-muted">
      <span>{count === 0 ? 'Sin resultados' : `${from}–${to} de ${count}`}</span>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Anterior
        </Button>
        <Button variant="secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Siguiente
        </Button>
      </div>
    </nav>
  );
}
