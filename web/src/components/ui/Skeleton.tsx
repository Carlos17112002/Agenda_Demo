export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div aria-label="Cargando" role="status" className="space-y-3">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="h-10 animate-pulse rounded-md bg-line" />
      ))}
    </div>
  );
}
