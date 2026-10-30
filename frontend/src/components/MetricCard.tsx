import clsx from "clsx";
import { ArrowDownRight, ArrowUpRight, GitBranch } from "lucide-react";
import type { ReactNode } from "react";
import { StatusBadge } from "./StatusBadge";

export function MetricCard({
  label,
  value,
  sub,
  delta,
  deltaLabel,
  status = "DETERMINISTIC",
  formulaId,
  onTrace,
  footnote,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  delta?: number | null;
  deltaLabel?: string;
  status?: string;
  formulaId?: string;
  onTrace?: () => void;
  footnote?: ReactNode;
}) {
  const incomplete = status !== "DETERMINISTIC";
  const Tag = onTrace ? "button" : "div";
  return (
    <Tag
      onClick={onTrace}
      className={clsx(
        "group flex min-w-0 flex-col rounded-lg border bg-white p-3.5 text-left shadow-card transition",
        onTrace && "hover:border-brand-500/50 hover:shadow-pop focus-visible:border-brand-500",
        incomplete ? "border-risk-100" : "border-ink-200/80",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="label-caps truncate" title={label}>{label}</span>
      </div>
      <div className={clsx("num mt-2 text-[22px] font-semibold leading-none tracking-tight", incomplete ? "text-ink-400" : "text-ink-950")}>{value}</div>
      <div className="mt-2 flex min-h-[18px] items-center gap-2 text-xs">
        {delta !== undefined && delta !== null && (
          <span className={clsx("num inline-flex items-center gap-0.5 font-medium", delta >= 0 ? "text-ok-700" : "text-risk-700")}>
            {delta >= 0 ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
            {deltaLabel}
          </span>
        )}
        {incomplete && <StatusBadge kind={status as any} size="xs" />}
        {sub && !incomplete && <span className="truncate text-ink-500">{sub}</span>}
      </div>
      {footnote && <div className="mt-1 text-[11px] text-ink-400">{footnote}</div>}
      {onTrace && (
        <span className="mt-2.5 inline-flex items-center gap-1 border-t border-ink-100 pt-2 text-[11px] font-medium text-ink-500 group-hover:text-brand-600">
          <GitBranch className="h-3 w-3" /> Trace
          {formulaId && <span className="ml-auto font-mono text-[10px] font-normal text-ink-400">{formulaId}</span>}
        </span>
      )}
    </Tag>
  );
}
