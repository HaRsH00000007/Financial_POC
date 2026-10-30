import clsx from "clsx";
import { AlertTriangle, CheckCircle2, CircleDashed, Loader2, ShieldCheck, Sparkles, XCircle, type LucideIcon } from "lucide-react";

export type BadgeKind =
  | "VALID"
  | "VERIFIED"
  | "DETERMINISTIC"
  | "WARNING"
  | "REVIEW_REQUIRED"
  | "INCOMPLETE"
  | "UNDEFINED"
  | "PROCESSING"
  | "ERROR"
  | "AI"
  | "NEUTRAL";

const MAP: Record<BadgeKind, { cls: string; icon: LucideIcon; label: string }> = {
  VALID: { cls: "bg-ok-50 text-ok-700 ring-ok-100", icon: CheckCircle2, label: "Valid" },
  VERIFIED: { cls: "bg-ok-50 text-ok-700 ring-ok-100", icon: ShieldCheck, label: "Verified" },
  DETERMINISTIC: { cls: "bg-ok-50 text-ok-700 ring-ok-100", icon: ShieldCheck, label: "Deterministic" },
  WARNING: { cls: "bg-warn-50 text-warn-700 ring-warn-100", icon: AlertTriangle, label: "Warning" },
  REVIEW_REQUIRED: { cls: "bg-risk-50 text-risk-700 ring-risk-100", icon: XCircle, label: "Review required" },
  INCOMPLETE: { cls: "bg-risk-50 text-risk-700 ring-risk-100", icon: CircleDashed, label: "Incomplete" },
  UNDEFINED: { cls: "bg-ink-100 text-ink-600 ring-ink-200", icon: CircleDashed, label: "Undefined" },
  PROCESSING: { cls: "bg-brand-50 text-brand-700 ring-brand-100", icon: Loader2, label: "Processing" },
  ERROR: { cls: "bg-risk-50 text-risk-700 ring-risk-100", icon: XCircle, label: "Error" },
  AI: { cls: "bg-ai-50 text-ai-700 ring-ai-100", icon: Sparkles, label: "AI" },
  NEUTRAL: { cls: "bg-ink-100 text-ink-600 ring-ink-200", icon: CircleDashed, label: "" },
};

export function StatusBadge({ kind, label, className, size = "sm" }: { kind: BadgeKind; label?: string; className?: string; size?: "xs" | "sm" }) {
  const m = MAP[kind] ?? MAP.NEUTRAL;
  const Icon = m.icon;
  return (
    <span
      className={clsx(
        "inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full font-medium ring-1 ring-inset",
        size === "xs" ? "px-1.5 py-0 text-[10.5px] leading-[18px]" : "px-2 py-0.5 text-[11.5px]",
        m.cls,
        className,
      )}
    >
      <Icon className={clsx(size === "xs" ? "h-3 w-3" : "h-3.5 w-3.5", kind === "PROCESSING" && "animate-spin")} aria-hidden />
      {label ?? m.label}
    </span>
  );
}

/** Small chip naming the architectural layer that produced something. */
export function LayerTag({ layer }: { layer: "probabilistic" | "deterministic" | "trust" | "orchestration" | "human" }) {
  const map = {
    probabilistic: "bg-ai-50 text-ai-700 ring-ai-100",
    deterministic: "bg-brand-50 text-brand-700 ring-brand-100",
    trust: "bg-ok-50 text-ok-700 ring-ok-100",
    orchestration: "bg-ink-100 text-ink-700 ring-ink-200",
    human: "bg-warn-50 text-warn-700 ring-warn-100",
  } as const;
  const label = {
    probabilistic: "Probabilistic AI",
    deterministic: "Deterministic engine",
    trust: "Trust & audit",
    orchestration: "Orchestration",
    human: "Human review",
  }[layer];
  return <span className={clsx("inline-flex items-center rounded px-1.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ring-1 ring-inset", map[layer])}>{label}</span>;
}
