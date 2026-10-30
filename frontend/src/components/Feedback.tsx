import clsx from "clsx";
import { AlertOctagon, CheckCircle2, Inbox, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "./Button";

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: {
  icon?: LucideIcon;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("flex flex-col items-center justify-center px-6 py-12 text-center", className)}>
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg border border-ink-200 bg-ink-50 text-ink-500">
        <Icon className="h-5 w-5" />
      </div>
      <h4 className="text-sm font-semibold text-ink-900">{title}</h4>
      {description && <p className="mt-1 max-w-md text-[13px] text-ink-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function LoadingState({ lines = 4, className }: { lines?: number; className?: string }) {
  return (
    <div className={clsx("space-y-2.5 p-4", className)} aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton h-4" style={{ width: `${90 - ((i * 17) % 40)}%` }} />
      ))}
    </div>
  );
}

export function ErrorState({ title = "Something went wrong", message, onRetry }: { title?: string; message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-risk-100 bg-risk-50 p-4">
      <AlertOctagon className="mt-0.5 h-4 w-4 shrink-0 text-risk-600" />
      <div className="flex-1">
        <p className="text-[13px] font-semibold text-risk-700">{title}</p>
        <p className="mt-0.5 text-[13px] text-risk-700/90">{message}</p>
      </div>
      {onRetry && (
        <Button size="sm" variant="danger" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function SuccessState({ title, message }: { title: string; message?: string }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-ok-100 bg-ok-50 p-4">
      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok-600" />
      <div>
        <p className="text-[13px] font-semibold text-ok-700">{title}</p>
        {message && <p className="mt-0.5 text-[13px] text-ok-700/90">{message}</p>}
      </div>
    </div>
  );
}

export function Callout({ tone = "neutral", icon: Icon, children, className }: { tone?: "neutral" | "ai" | "warn" | "brand"; icon?: LucideIcon; children: ReactNode; className?: string }) {
  const tones = {
    neutral: "border-ink-200 bg-ink-50 text-ink-700",
    ai: "border-ai-100 bg-ai-50 text-ai-700",
    warn: "border-warn-100 bg-warn-50 text-warn-700",
    brand: "border-brand-100 bg-brand-50 text-brand-700",
  };
  return (
    <div className={clsx("flex items-start gap-2 rounded-md border px-3 py-2 text-xs", tones[tone], className)}>
      {Icon && <Icon className="mt-px h-3.5 w-3.5 shrink-0" />}
      <div>{children}</div>
    </div>
  );
}
