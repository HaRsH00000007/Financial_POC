import { ArrowRight, CheckCircle2, Cpu, XCircle } from "lucide-react";
import { Button } from "@/components/Button";
import { Card, CardHeader } from "@/components/Card";
import { Callout } from "@/components/Feedback";
import { LayerTag, StatusBadge } from "@/components/StatusBadge";
import { AgentTimeline } from "@/features/t12/AgentTimeline";
import { metricName, money, periodLabel, plain } from "@/lib/format";
import type { AnnualModelResponse, Identity, Workspace } from "@/types";

const STATEMENT_LABEL: Record<string, string> = {
  income_statement: "Statement of Profit and Loss",
  balance_sheet: "Balance Sheet",
  cash_flow: "Cash Flow Statement",
  cross_statement: "Cross-statement",
};

export function AnnualCalculationStep({ ws, data, onNext }: { ws: Workspace; data: AnnualModelResponse; onNext: () => void }) {
  const m = data.model;
  const calcRun = [...ws.agent_runs].reverse().find((r) => r.agent === "Calculation Agent");
  const o = (calcRun?.outputs ?? {}) as any;
  const passed = m.identities.filter((i) => i.matches).length;
  const groups: Record<string, Record<string, Identity[]>> = {};
  m.identities.forEach((i) => ((groups[i.statement] ??= {})[i.id] ??= []).push(i));

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
              ["Fiscal years", m.periods.length ? `${periodLabel(m.periods[0], true)} – ${periodLabel(m.periods[m.periods.length - 1], true)}` : "—"],
              ["Identity checks", `${passed}/${m.identities.length}`],
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
            {Object.keys(m.not_printed).length > 0 && (
              <p className="mt-3 text-xs text-ink-500">
                Optional lines not printed in the statement used for a year (excluded for that year, not zero-filled):{" "}
                {Object.entries(m.not_printed)
                  .map(([p, ks]) => `${periodLabel(p, true)}: ${ks.map(metricName).join(", ")}`)
                  .join(" · ")}
                .
              </p>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Accounting identity checks" subtitle="Every printed subtotal is recomputed from its components, per fiscal year, within rounding tolerance" />
          <div className="grid gap-4 p-4 md:grid-cols-2">
            {Object.entries(groups).map(([st, ids]) => (
              <div key={st}>
                <div className="label-caps mb-2">{STATEMENT_LABEL[st] ?? st}</div>
                <ul className="space-y-1.5">
                  {Object.entries(ids).map(([id, recs]) => {
                    const bad = recs.filter((r) => !r.matches);
                    return (
                      <li key={id} className="flex items-center justify-between gap-2 text-[13px]">
                        <span className="flex items-center gap-1.5">
                          {bad.length ? <XCircle className="h-3.5 w-3.5 text-risk-600" /> : <CheckCircle2 className="h-3.5 w-3.5 text-ok-600" />}
                          {recs[0].name ?? metricName(recs[0].metric)}
                        </span>
                        {bad.length ? (
                          <StatusBadge kind="WARNING" size="xs" label={bad.map((b) => `${periodLabel(b.period, true)} ${plain(b.variance)}`).join(", ")} />
                        ) : (
                          <span className="text-[11px] text-ink-500">{recs.length} yr{recs.length > 1 ? "s" : ""}</span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        </Card>

        {m.restatements.length > 0 && (
          <Card>
            <CardHeader title="Restated comparatives" subtitle="The same fiscal year printed differently in two reports. The later report's figure is used." />
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead className="bg-ink-50 text-left text-[10.5px] uppercase tracking-wide text-ink-500">
                  <tr>
                    <th className="px-4 py-2 font-medium">Line</th>
                    <th className="px-2 py-2 font-medium">Year</th>
                    <th className="px-2 py-2 text-right font-medium">Earlier report</th>
                    <th className="px-2 py-2 text-right font-medium">Later report (used)</th>
                    <th className="px-4 py-2 text-right font-medium">Difference</th>
                  </tr>
                </thead>
                <tbody className="num divide-y divide-ink-100">
                  {m.restatements.map((r, i) => (
                    <tr key={i}>
                      <td className="px-4 py-2 font-sans text-ink-900">{r.name}</td>
                      <td className="px-2 py-2">{periodLabel(r.period, true)}</td>
                      <td className="px-2 py-2 text-right" title={r.original_document}>{money(r.original)}</td>
                      <td className="px-2 py-2 text-right" title={r.restated_document}>{money(r.restated)}</td>
                      <td className="px-4 py-2 text-right font-medium text-warn-700">{plain(r.difference)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
        {data.incomplete.length > 0 && (
          <Callout tone="warn">
            {data.incomplete.length} value(s) are INCOMPLETE or UNDEFINED because inputs are missing (
            {[...new Set(data.incomplete.map((i) => metricName(i.metric)))].slice(0, 6).join(", ")}). They are shown as blanks, never estimated.
          </Callout>
        )}
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
            Open analysis
          </Button>
        </div>
      </div>
    </div>
  );
}
