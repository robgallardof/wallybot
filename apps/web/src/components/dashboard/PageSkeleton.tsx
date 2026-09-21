export function PageSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="page-skeleton" aria-busy="true" aria-label="Cargando contenido">
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
