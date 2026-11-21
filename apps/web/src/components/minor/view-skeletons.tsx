import { Skeleton } from "@/components/minor/skeleton";
import { Panel } from "@/components/ui";

function SkeletonHeader({
  eyebrowWidth = "w-32",
  titleWidth = "w-72",
  showBadge = false,
}: {
  eyebrowWidth?: string;
  titleWidth?: string;
  showBadge?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="space-y-2 min-w-0 flex-1">
        <Skeleton className={`h-3 ${eyebrowWidth} rounded-lg`} />
        <Skeleton className={`h-8 ${titleWidth} max-w-full rounded-lg`} />
      </div>
      {showBadge && <Skeleton className="h-6 w-28 shrink-0 rounded-lg" />}
    </div>
  );
}

export function PlanSkeleton() {
  return (
    <div className="space-y-5" role="status" aria-busy="true" aria-label="Loading learning path">
      <span className="sr-only">Loading…</span>
      <SkeletonHeader eyebrowWidth="w-36" titleWidth="w-80" showBadge />
      <Panel className="space-y-3">
        <div className="flex flex-wrap items-center gap-4">
          <Skeleton className="h-7 w-24 rounded-lg" />
          <Skeleton className="h-2.5 flex-1 min-w-[140px] rounded-lg" />
          <Skeleton className="h-6 w-20 rounded-lg" />
        </div>
      </Panel>
      <div className="grid gap-3">
        {[0, 1, 2, 3].map((item) => (
          <Panel key={item} className="flex flex-row items-center gap-4">
            <Skeleton className="h-9 w-9 shrink-0 rounded-full" />
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-3 w-28 rounded-lg" />
              <Skeleton className="h-5 w-60 max-w-full rounded-lg" />
              <Skeleton className="h-3.5 w-3/4 rounded-lg" />
            </div>
            <Skeleton className="h-8 w-8 shrink-0 rounded-lg" />
          </Panel>
        ))}
      </div>
    </div>
  );
}

export function LessonSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-busy="true" aria-label="Loading lesson">
      <span className="sr-only">Loading…</span>
      <div className="space-y-2">
        <Skeleton className="h-3 w-32 rounded-lg" />
        <Skeleton className="h-8 w-80 max-w-full rounded-lg" />
      </div>
      <Panel className="space-y-5">
        <Skeleton className="h-5 w-28 rounded-lg" />
        {[0, 1, 2].map((section) => (
          <div key={section} className="flex items-start gap-4">
            <Skeleton className="h-6 w-8 shrink-0 rounded-lg" />
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-5 w-48 max-w-full rounded-lg" />
              <Skeleton className="h-3.5 w-full rounded-lg" />
              <Skeleton className="h-3.5 w-5/6 rounded-lg" />
            </div>
          </div>
        ))}
      </Panel>
      <Panel className="space-y-4">
        <Skeleton className="h-3 w-36 rounded-lg" />
        <Skeleton className="h-5 w-4/5 rounded-lg" />
        <div className="space-y-2.5">
          {[0, 1, 2].map((option) => (
            <Skeleton key={option} className="h-11 w-full rounded-lg" />
          ))}
        </div>
      </Panel>
    </div>
  );
}

export function ScenarioSkeleton() {
  return (
    <div
      className="space-y-5"
      role="status"
      aria-busy="true"
      aria-label="Loading practice scenario"
    >
      <span className="sr-only">Loading…</span>
      <SkeletonHeader eyebrowWidth="w-36" titleWidth="w-72" showBadge />
      <div className="grid gap-4 lg:grid-cols-[1.25fr_0.75fr]">
        <div className="min-w-0 space-y-4">
          <Panel className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div className="space-y-2">
                <Skeleton className="h-3 w-36 rounded-lg" />
                <Skeleton className="h-5 w-48 max-w-full rounded-lg" />
              </div>
              <Skeleton className="h-5 w-24 rounded-lg" />
            </div>
            <Skeleton className="h-56 w-full rounded-lg" />
            <Skeleton className="h-3 w-44 rounded-lg" />
          </Panel>
          <Panel className="space-y-4">
            <div className="space-y-2">
              <Skeleton className="h-3 w-40 rounded-lg" />
              <Skeleton className="h-5 w-44 rounded-lg" />
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {[0, 1, 2].map((metric) => (
                <Skeleton key={metric} className="h-14 w-full rounded-lg" />
              ))}
            </div>
            <div className="space-y-2.5">
              <Skeleton className="h-12 w-full rounded-lg" />
              <Skeleton className="h-12 w-full rounded-lg" />
            </div>
          </Panel>
        </div>
        <div className="min-w-0">
          <Panel className="space-y-4">
            <Skeleton className="h-3 w-24 rounded-lg" />
            <Skeleton className="h-5 w-4/5 rounded-lg" />
            <div className="space-y-2.5">
              <Skeleton className="h-12 w-full rounded-lg" />
              <Skeleton className="h-12 w-full rounded-lg" />
            </div>
            <Skeleton className="h-12 w-full rounded-lg" />
            <div className="space-y-2">
              <Skeleton className="h-9 w-full rounded-lg" />
              <Skeleton className="h-9 w-full rounded-lg" />
              <Skeleton className="h-9 w-full rounded-lg" />
            </div>
            <Skeleton className="h-11 w-full rounded-lg" />
          </Panel>
        </div>
      </div>
    </div>
  );
}

export function ExplainSkeleton() {
  return (
    <div
      className="grid gap-4 md:grid-cols-2"
      role="status"
      aria-busy="true"
      aria-label="Loading stock explanation"
    >
      <span className="sr-only">Loading…</span>
      <Panel className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div className="space-y-2">
            <Skeleton className="h-3 w-24 rounded-lg" />
            <Skeleton className="h-5 w-44 rounded-lg" />
          </div>
          <Skeleton className="h-5 w-24 rounded-lg" />
        </div>
        <Skeleton className="h-60 w-full rounded-lg" />
        <Skeleton className="h-3 w-36 rounded-lg" />
      </Panel>
      <Panel className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <Skeleton className="h-3 w-28 rounded-lg" />
          <Skeleton className="h-5 w-24 rounded-lg" />
        </div>
        <div className="space-y-2">
          <Skeleton className="h-5 w-full rounded-lg" />
          <Skeleton className="h-5 w-4/5 rounded-lg" />
        </div>
        <div className="space-y-3 pt-1">
          {[0, 1, 2].map((move) => (
            <div key={move} className="grid grid-cols-[56px_1fr] gap-3">
              <Skeleton className="h-4 w-12 rounded-lg" />
              <div className="space-y-2">
                <Skeleton className="h-4 w-32 rounded-lg" />
                <Skeleton className="h-3.5 w-full rounded-lg" />
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

export function VerifierSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-busy="true" aria-label="Verifying message">
      <span className="sr-only">Loading…</span>
      <Panel className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <Skeleton className="h-11 w-11 shrink-0 rounded-full" />
            <div className="space-y-2">
              <Skeleton className="h-3 w-28 rounded-lg" />
              <Skeleton className="h-5 w-40 rounded-lg" />
            </div>
          </div>
          <Skeleton className="h-5 w-24 rounded-lg" />
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <Skeleton className="h-10 w-24 rounded-lg" />
          <div className="space-y-2 flex-1 min-w-[160px]">
            <Skeleton className="h-5 w-32 rounded-lg" />
            <Skeleton className="h-3.5 w-3/4 rounded-lg" />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {[0, 1, 2, 3].map((fact) => (
            <Skeleton key={fact} className="h-12 w-full rounded-lg" />
          ))}
        </div>
      </Panel>
      <Panel className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div className="space-y-2">
            <Skeleton className="h-3 w-28 rounded-lg" />
            <Skeleton className="h-6 w-36 rounded-lg" />
          </div>
          <Skeleton className="h-5 w-24 rounded-lg" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Skeleton className="h-10 w-full rounded-lg" />
          <Skeleton className="h-10 w-full rounded-lg" />
        </div>
        <div className="space-y-2.5">
          <Skeleton className="h-14 w-full rounded-lg" />
          <Skeleton className="h-14 w-full rounded-lg" />
        </div>
      </Panel>
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div
      className="space-y-5"
      role="status"
      aria-busy="true"
      aria-label="Loading progress dashboard"
    >
      <span className="sr-only">Loading…</span>
      <SkeletonHeader eyebrowWidth="w-28" titleWidth="w-72" showBadge />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[0, 1, 2].map((stat) => (
          <Panel key={stat} className="space-y-2.5">
            <Skeleton className="h-3 w-28 rounded-lg" />
            <Skeleton className="h-7 w-24 rounded-lg" />
            <Skeleton className="h-3 w-36 rounded-lg" />
          </Panel>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {[0, 1].map((chart) => (
          <Panel key={chart} className="space-y-3">
            <Skeleton className="h-5 w-44 rounded-lg" />
            <Skeleton className="h-56 w-full rounded-lg" />
          </Panel>
        ))}
      </div>
      <Panel className="space-y-2.5">
        <Skeleton className="h-3 w-32 rounded-lg" />
        <Skeleton className="h-5 w-60 max-w-full rounded-lg" />
        <Skeleton className="h-3.5 w-full rounded-lg" />
        <Skeleton className="h-3.5 w-4/5 rounded-lg" />
      </Panel>
    </div>
  );
}
