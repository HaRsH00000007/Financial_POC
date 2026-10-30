import { ArrowRight, CheckCircle2, CircleDashed, Cpu, XCircle } from "lucide-react";
import { Button } from "@/components/Button";
import { Card, CardHeader } from "@/components/Card";
import { Callout } from "@/components/Feedback";
import { LayerTag, StatusBadge } from "@/components/StatusBadge";
import { metricName, money, periodLabel } from "@/lib/format";
import type { ModelResponse, Workspace } from "@/types";
import { AgentTimeline } from "./AgentTimeline";

export function CalculationStep({ ws, model, onNext }: { ws: Workspace; model: ModelResponse; onNext: () => void }) {
  const m = model.model;
  const calcRun = [...ws.agent_runs].reverse().find((r) => r.agent === "Calculation Agent");
  const o = (calcRun?.outputs ?? {}) as any;
  const breaks = m.reconciliations.filter((r) => !r.matches);
  const recMetrics = [...new Set(m.reconciliations.map((r) => r.metric))];

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <div className="space-y-4">
        <Card>
          <CardHeader
            icon={<Cpu className="h-4 w-4" />}
            title="Deterministic engine run"
            subtitle={`${m.engine} · exact Decimal arithmetic · formulas parsed as data (no eval)`}
            actions={<LayerTag layer="deterministic" />}
          />
          <div className="grid grid-cols-2 gap-px bg-ink-100 sm:grid-cols-4">
            {[
              ["Formula results", o.formulas_evaluated ?? "—"],
              ["T-12 window", m.window.length ? `${periodLabel(m.window[0], true)} – ${periodLabel(m.window[m.window.length - 1], true)}` : "—"],
              ["Incomplete values", model.incomplete.length],
              ["LLM involvement", "None"],
            ].map(([k, v]) => (
              <div key={k as string} className="bg-white px-4 py-3">
                <div className="label-caps">{k}</div>
                <div className="num mt-1 text-[17px] font-semibold text-ink-950">{v}</div>
              </div>
            ))}
          </div>
          <div className="p-4">
            <div className="label-caps mb-2">Evaluation order (topological)</div>
            <div className="flex flex-wrap items-center gap-1.5">
              {(o.evaluation_order ?? []).map((k: string, i: number, arr: string[]) => (
                <span key={k} className="flex items-center gap-1.5">
                  <span className="rounded bg-brand-50 px-2 py-1 font-mono text-[11.5px] text-brand-700 ring-1 ring-brand-100">{k}</span>
                  {i < arr.length - 1 && <ArrowRight className="h-3 w-3 text-ink-300" />}
                </span>
              ))}
            </div>
            {m.not_reported.length > 0 && (
              <p className="mt-3 text-xs text-ink-500">
                Not reported in source (excluded, not zero-filled): {m.not_reported.map(metricName).join(", ")}.
              </p>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Integrity checks" subtitle="Independent deterministic checks on the model" />
          <div className="grid gap-4 p-4 md:grid-cols-2">
            <div>
              <div className="label-caps mb-2">Cross-foot · formula on T-12 totals = Σ months</div>
              <ul className="space-y-1.5">
                {m.crossfoot.map((c) => (
                  <li key={c.metric} className="flex items-center justify-between text-[13px]">
                    <span className="flex items-center gap-1.5">
                      {c.passed ? <CheckCircle2 className="h-3.5 w-3.5 text-ok-600" /> : <XCircle className="h-3.5 w-3.5 text-risk-600" />}
                      {metricName(c.metric)}
                    </span>
                    <span className="num text-xs text-ink-500">{money(c.sum_of_months)}</span>
                  </li>
                ))}
                {m.crossfoot.length === 0 && <li className="flex items-center gap-1.5 text-xs text-ink-500"><CircleDashed className="h-3.5 w-3.5" /> Skipped — T-12 totals incomplete.</li>}
              </ul>
            </div>
            <div>
              <div className="label-caps mb-2">Reconciliation to printed subtotals</div>
              <ul className="space-y-1.5">
                {recMetrics.map((k) => {
                  const b = breaks.filter((r) => r.metric === k);
                  return (
                    <li key={k} className="flex items-center justify-between gap-2 text-[13px]">
                      <span>{metricName(k)}</span>
                      {b.length ? <StatusBadge kind="WARNING" size="xs" label={`${b.length} break${b.length > 1 ? "s" : ""}: ${b.map((x) => periodLabel(x.period, true)).join(", ")}`} /> : <StatusBadge kind="VALID" size="xs" label="Reconciles" />}
                    </li>
                  );
                })}
                {recMetrics.length === 0 && <li className="text-xs text-ink-500">No subtotals printed in the source.</li>}
              </ul>
            </div>
          </div>
          {model.incomplete.length > 0 && (
            <div className="px-4 pb-4">
              <Callout tone="warn">
                {model.incomplete.length} monthly value(s) are INCOMPLETE because inputs are missing (
                {[...new Set(model.incomplete.map((i) => periodLabel(i.period)))].join(", ")}). They are shown as blanks, and any T-12 total that depends on them is also
                INCOMPLETE.
              </Callout>
            </div>
          )}
        </Card>
      </div>
      <div className="space-y-4">
        <Card>
          <CardHeader title="Agent activity" />
          <div className="p-4">
            <AgentTimeline runs={ws.agent_runs} limit={4} />
          </div>
        </Card>
        <div className="flex justify-end">
          <Button variant="primary" size="lg" onClick={onNext} iconRight={<ArrowRight className="h-4 w-4" />}>
            Open financial dashboard
          </Button>
        </div>
      </div>
    </div>
  );
}
