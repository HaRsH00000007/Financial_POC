import clsx from "clsx";
import { ArrowDown, Brain, Calculator, FileSearch, ShieldCheck, type LucideIcon } from "lucide-react";

const LAYERS: { key: string; title: string; subtitle: string; icon: LucideIcon; tone: string; items: string[] }[] = [
  {
    key: "ai",
    title: "AI Reasoning",
    subtitle: "Probabilistic · generative AI & agents",
    icon: Brain,
    tone: "ai",
    items: ["Document classification", "Label → taxonomy suggestions", "Narrative commentary", "Natural-language Q&A", "Agent orchestration"],
  },
  {
    key: "det",
    title: "Deterministic Calculation",
    subtitle: "Exact Decimal formula engine",
    icon: Calculator,
    tone: "brand",
    items: ["Formula evaluation (AST, no eval)", "Category aggregation", "T-12 totals & ratios", "Reconciliation & cross-foot", "Missing inputs → INCOMPLETE"],
  },
  {
    key: "trust",
    title: "Data Trust & Auditability",
    subtitle: "Provenance, lineage, human review",
    icon: ShieldCheck,
    tone: "ok",
    items: ["Page / sheet / cell source refs", "Formula lineage trees", "Hash-chained audit log", "Reviewer overrides w/ justification", "Numeric-claim guard on AI text"],
  },
];

const TONES: Record<string, { box: string; icon: string; chip: string }> = {
  ai: { box: "border-ai-100 bg-ai-50/50", icon: "bg-ai-600 text-white", chip: "bg-white text-ai-700 ring-ai-100" },
  brand: { box: "border-brand-100 bg-brand-50/60", icon: "bg-brand-600 text-white", chip: "bg-white text-brand-700 ring-brand-100" },
  ok: { box: "border-ok-100 bg-ok-50/60", icon: "bg-ok-600 text-white", chip: "bg-white text-ok-700 ring-ok-100" },
};

export function LayerStack({ compact }: { compact?: boolean }) {
  return (
    <div className="flex flex-col items-stretch">
      {LAYERS.map((l, i) => {
        const t = TONES[l.tone];
        return (
          <div key={l.key}>
            <div className={clsx("rounded-lg border p-3.5", t.box)}>
              <div className="flex items-center gap-2.5">
                <div className={clsx("flex h-7 w-7 items-center justify-center rounded-md", t.icon)}>
                  <l.icon className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-[13px] font-semibold text-ink-950">{l.title}</div>
                  <div className="text-[11.5px] text-ink-500">{l.subtitle}</div>
                </div>
              </div>
              {!compact && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {l.items.map((it) => (
                    <span key={it} className={clsx("rounded px-1.5 py-0.5 text-[11px] ring-1 ring-inset", t.chip)}>
                      {it}
                    </span>
                  ))}
                </div>
              )}
            </div>
            {i < LAYERS.length - 1 && (
              <div className="flex justify-center py-1 text-ink-300">
                <ArrowDown className="h-4 w-4" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function PipelineFlow() {
  const steps = [
    { label: "User", tone: "neutral", note: "Upload / question" },
    { label: "AI / Orchestration", tone: "ai", note: "Coordinator agent" },
    { label: "Extraction + Normalization", tone: "ai", note: "Rules first, AI assist" },
    { label: "Deterministic Engine", tone: "brand", note: "Every number" },
    { label: "Audit / Traceability", tone: "ok", note: "Lineage + log" },
    { label: "AI Insights", tone: "ai", note: "On verified outputs" },
  ];
  const cls: Record<string, string> = {
    neutral: "border-ink-200 bg-white",
    ai: "border-ai-100 bg-ai-50/60",
    brand: "border-brand-100 bg-brand-50",
    ok: "border-ok-100 bg-ok-50",
  };
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
      {steps.map((s, i) => (
        <div key={s.label} className={clsx("relative rounded-md border px-3 py-2.5", cls[s.tone])}>
          <div className="text-[10.5px] font-semibold text-ink-400">{String(i + 1).padStart(2, "0")}</div>
          <div className="text-[12.5px] font-semibold text-ink-900">{s.label}</div>
          <div className="text-[11px] text-ink-500">{s.note}</div>
        </div>
      ))}
    </div>
  );
}

export function PlatformModules() {
  return (
    <div className="rounded-lg border border-ink-200 bg-white p-4">
      <div className="mx-auto w-fit rounded-md bg-ink-950 px-3 py-1.5 text-xs font-semibold text-white">Finance Intelligence Workbench</div>
      <div className="mx-auto h-4 w-px bg-ink-300" />
      <div className="mx-auto h-px w-2/3 bg-ink-300" />
      <div className="grid grid-cols-2 gap-3">
        {[
          { t: "T-12 Financial Spreading", i: FileSearch },
          { t: "Enterprise AI Evaluation", i: ShieldCheck },
        ].map((m) => (
          <div key={m.t} className="flex flex-col items-center">
            <div className="h-4 w-px bg-ink-300" />
            <div className="flex w-full items-center justify-center gap-1.5 rounded-md border border-ink-200 bg-ink-50 px-2 py-2 text-center text-[12px] font-medium text-ink-800">
              <m.i className="h-3.5 w-3.5 text-ink-500" /> {m.t}
            </div>
          </div>
        ))}
      </div>
      <div className="mx-auto h-4 w-px bg-ink-300" />
      <div className="rounded-md border border-dashed border-ink-300 p-2.5">
        <div className="mb-2 text-center text-[10.5px] font-semibold uppercase tracking-wider text-ink-500">Shared AI platform</div>
        <div className="grid grid-cols-3 gap-2 text-center text-[11.5px] font-medium">
          <div className="rounded bg-ai-50 px-2 py-1.5 text-ai-700 ring-1 ring-inset ring-ai-100">LLM layer</div>
          <div className="rounded bg-ink-100 px-2 py-1.5 text-ink-700 ring-1 ring-inset ring-ink-200">Agent layer</div>
          <div className="rounded bg-ok-50 px-2 py-1.5 text-ok-700 ring-1 ring-inset ring-ok-100">Audit layer</div>
        </div>
      </div>
    </div>
  );
}

export function Responsibilities() {
  const cols = [
    {
      title: "Probabilistic AI",
      tone: "ai",
      items: ["Document understanding", "Classification", "Extraction assistance", "Natural language", "Narrative generation", "Anomaly / risk patterns", "User interaction", "Agent orchestration"],
    },
    {
      title: "Deterministic engine",
      tone: "brand",
      items: ["Arithmetic", "Formula evaluation", "Financial aggregation", "Ratio calculations", "T-12 calculations", "Reconciliation", "Validation", "Financial model outputs"],
    },
    {
      title: "Trust / audit",
      tone: "ok",
      items: ["Source references", "Formula lineage", "Calculation history", "Immutable audit events", "Human review", "Data provenance"],
    },
  ];
  const dot: Record<string, string> = { ai: "bg-ai-600", brand: "bg-brand-500", ok: "bg-ok-600" };
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {cols.map((c) => (
        <div key={c.title} className="rounded-lg border border-ink-200 bg-white p-4">
          <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-ink-950">
            <span className={clsx("h-2 w-2 rounded-full", dot[c.tone])} />
            {c.title}
          </div>
          <ul className="space-y-1 text-[12.5px] text-ink-600">
            {c.items.map((i) => (
              <li key={i}>{i}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
