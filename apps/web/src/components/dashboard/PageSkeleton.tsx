export function PageSkeleton({
  rows = 3,
  label = "Cargando contenido",
}: {
  rows?: number;
  label?: string;
}) {
  return (
    <div className="page-skeleton" aria-busy="true" role="status">
      <span className="visually-hidden">{label}</span>
      <span className="skeleton-line skeleton-kicker" />
      <span className="skeleton-line skeleton-title" />
      <span className="skeleton-line skeleton-copy" />
      <div className="skeleton-cards">
        {Array.from({ length: rows }, (_, index) => (
          <span className="skeleton-card" key={index} />
        ))}
      </div>
    </div>
  );
}
