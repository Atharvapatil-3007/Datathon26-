import clsx from "clsx";

/**
 * Basic shimmer skeleton primitive. Compose it into placeholders for
 * cards, tables, lists, etc.
 */
export function Skeleton({
  className,
  as: Tag = "div",
}: {
  className?: string;
  as?: keyof JSX.IntrinsicElements;
}) {
  return <Tag className={clsx("skeleton", className)} aria-hidden />;
}

/** Common placeholder for a KPI card row. */
export function MetricSkeletonRow({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-xl border border-line bg-bg-card p-4">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="mt-3 h-6 w-24" />
          <Skeleton className="mt-2 h-3 w-16" />
        </div>
      ))}
    </div>
  );
}

/** Placeholder for a page hero + first content block. */
export function PageSkeleton() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="h-4 w-40" />
        <Skeleton className="mt-3 h-7 w-72" />
        <Skeleton className="mt-2 h-3 w-96" />
      </div>
      <MetricSkeletonRow />
      <div className="rounded-xl border border-line bg-bg-card p-5 space-y-3">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    </div>
  );
}
