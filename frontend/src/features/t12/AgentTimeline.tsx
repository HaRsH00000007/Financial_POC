import clsx from "clsx";
import { Bot, Brain, Calculator, CheckCircle2, ClipboardCheck, FileSearch, Network, XCircle } from "lucide-react";
import { LayerTag } from "@/components/StatusBadge";
import type { AgentRun } from "@/types";

const ICONS: Record<string, any> = {
  Coordinator: Network,
  "Ingestion Agent": FileSearch,
  "Normalization Agent": Brain,
  "Validation Agent": ClipboardCheck,
  "Calculation Agent": Calculator,
  "Synthesis Agent": Bot,
};

function summarize(run: AgentRun): string {
  const o = run.outputs as any;
  switch (run.agent) {
    case "Coordinator":
      return `Plan: ${(o.plan ?? []).join(" → ")}`;
    case "Ingestion Agent":
      return `${o.document_type ?? "Document"} · ${o.rows} rows · ${o.periods} periods${o.pages ? ` · ${o.pages} pages` : ""}${o.scale && o.scale !== 1 ? ` · scale ×${o.scale}` : ""}`;
    case "Normalization Agent":
      return `${Object.entries(o.methods ?? {}).map(([k, v]) => `${v} ${k.replace("_", " ")}`).join(" · ")}${o.ai_suggestions_applied ? ` · ${o.ai_suggestions_applied} AI-suggested` : ""}`;
    case "Validation Agent":
      return `${o.counts?.VALID ?? 0} valid · ${o.counts?.WARNING ?? 0} warnings · ${o.counts?.REVIEW_REQUIRED ?? 0} require review`;
    case "Calculation Agent":
      return `${o.formulas_evaluated} formula results · ${o.reconciliation_breaks} reconciliation breaks · ${o.incomplete_values} incomplete · LLM involved: no`;
    case "Synthesis Agent":
      return `${o.provider} · figures verified ${o.numeric_check?.verified}/${o.numeric_check?.checked}`;
    default:
      return run.action;
  }
}

export function AgentTimeline({ runs, limit }: { runs: AgentRun[]; limit?: number }) {
  const shown = limit ? runs.slice(-limit) : runs;
  return (
    <ol className="space-y-0">
      {shown.map((r, i) => {
        const Icon = ICONS[r.agent] ?? Bot;
        const layer = r.layer === "deterministic" ? "deterministic" : r.layer === "probabilistic" ? "probabilistic" : "orchestration";
        return (
          <li key={r.id} className="relative flex gap-3 pb-3 last:pb-0">
            {i < shown.length - 1 && <span className="absolute left-[13px] top-7 h-[calc(100%-20px)] w-px bg-ink-200" />}
            <div
              className={clsx(
                "relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ring-1",
                layer === "deterministic" ? "bg-brand-50 text-brand-700 ring-brand-100" : layer === "probabilistic" ? "bg-ai-50 text-ai-700 ring-ai-100" : "bg-ink-100 text-ink-600 ring-ink-200",
              )}
            >
              <Icon className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[13px] font-medium text-ink-900">{r.agent}</span>
                <LayerTag layer={layer} />
                {r.status === "completed" ? <CheckCircle2 className="h-3.5 w-3.5 text-ok-600" /> : <XCircle className="h-3.5 w-3.5 text-risk-600" />}
                <span className="num ml-auto text-[11px] text-ink-400">{r.duration_ms} ms</span>
              </div>
              <div className="text-xs text-ink-500">{r.action}</div>
              <div className="mt-0.5 text-xs text-ink-700">{summarize(r)}</div>
              {r.error && <div className="mt-0.5 text-xs text-risk-700">{r.error}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
