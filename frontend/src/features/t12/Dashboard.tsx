import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/Button";
import { Card, CardHeader } from "@/components/Card";
import { HorizontalBars, MonthlyBarChart, MultiLineChart } from "@/components/FinancialChart";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge } from "@/components/StatusBadge";
import { metricName, money, pct, periodLabel } from "@/lib/format";
import type { ModelResponse } from "@/types";
import { Commentary } from "./Commentary";

export function Dashboard({
  workspaceId,
  data,
  onTrace,
  stale,
  onRecalculate,
  recalculating,
}: {
  workspaceId: string;
  data: ModelResponse;
  onTrace: (metric: string, period: string) => void;
  stale: boolean;
  onRecalculate: () => void;
  recalculating: boolean;
}) {
  const m = data.model;
  const t = m.t12;
  const series = m.window.map((p) => ({
    period: p,
    revenue: m.values.revenue?.[p] ?? null,
    ebitda: m.values.ebitda?.[p] ?? null,
    gross_margin: m.values.gross_margin?.[p] ?? null,
    ebitda_margin: m.values.ebitda_margin?.[p] ?? null,
    net_margin: m.values.net_margin?.[p] ?? null,
  }));
  const expenseKeys = ["cogs", ...m.opex_components, "depreciation", "interest", "taxes"].filter((k) => t[k]);
  const expenses = expenseKeys
    .map((k) => ({ key: k, name: metricName(k), value: t[k].result }))
    .sort((a, b) => (b.value ?? -1) - (a.value ?? -1));
  const g = m.growth.revenue;
  const version = `${m.t12.net_income?.result}-${m.t12.revenue?.result}-${data.check_summary.total}`;

  const kpi = (key: string) => t[key] ?? null;

  return (
    <div className="space-y-4">
      {stale && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-warn-100 bg-warn-50 px-4 py-2.5 text-[13px] text-warn-700">
          <AlertTriangle className="h-4 w-4" />
          Mappings or resolutions changed since the last calculation. Figures below reflect the previous run.
          <Button size="sm" className="ml-auto" onClick={onRecalculate} loading={recalculating} icon={<RefreshCw className="h-3.5 w-3.5" />}>
            Recalculate
          </Button>
        </div>
      )}

      {!m.window_complete ? (
        <Card className="p-4">
          <StatusBadge kind="REVIEW_REQUIRED" label="Fewer than 12 months" />
          <p className="mt-2 text-[13px] text-ink-600">The source contains {m.window.length} months. A T-12 cannot be computed and will not be extrapolated.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <MetricCard label="Revenue · T-12" value={money(kpi("revenue")?.result ?? null, { compact: true })} status={kpi("revenue")?.status} formulaId="T12_001" onTrace={() => onTrace("revenue", "T12")} />
          <MetricCard
            label="Gross Profit · T-12"
            value={money(kpi("gross_profit")?.result ?? null, { compact: true })}
            sub={`${pct(kpi("gross_margin")?.result)} margin`}
            status={kpi("gross_profit")?.status}
            formulaId="GP_001"
            onTrace={() => onTrace("gross_profit", "T12")}
          />
          <MetricCard label="EBITDA · T-12" value={money(kpi("ebitda")?.result ?? null, { compact: true })} status={kpi("ebitda")?.status} formulaId="EBITDA_001" onTrace={() => onTrace("ebitda", "T12")} />
          <MetricCard label="EBITDA Margin" value={pct(kpi("ebitda_margin")?.result)} status={kpi("ebitda_margin")?.status} formulaId="EBITDAM_001" onTrace={() => onTrace("ebitda_margin", "T12")} />
          <MetricCard label="Net Income · T-12" value={money(kpi("net_income")?.result ?? null, { compact: true })} sub={`${pct(kpi("net_margin")?.result)} margin`} status={kpi("net_income")?.status} formulaId="NI_001" onTrace={() => onTrace("net_income", "T12")} />
          <MetricCard
            label="Revenue Growth · YoY"
            value={g ? pct(g.result, true) : "n/a"}
            status={g ? g.status : "DETERMINISTIC"}
            formulaId="GROWTH_001"
            sub={g ? "vs prior T-12" : undefined}
            footnote={g ? undefined : "Needs 24 months of data — not computable"}
            onTrace={g ? () => onTrace("revenue", "YOY") : undefined}
          />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Revenue trend" subtitle="Monthly revenue in the T-12 window · click a bar to trace" />
          <div className="px-2 pb-3 pt-2">
            <MonthlyBarChart data={series} dataKey="revenue" name="Revenue" onSelect={(p) => onTrace("revenue", p)} />
          </div>
        </Card>
        <Card>
          <CardHeader title="EBITDA trend" subtitle="EBITDA_001 per month · gaps are INCOMPLETE months" />
          <div className="px-2 pb-3 pt-2">
            <MonthlyBarChart data={series} dataKey="ebitda" name="EBITDA" onSelect={(p) => onTrace("ebitda", p)} />
          </div>
        </Card>
        <Card>
          <CardHeader title="Expense breakdown" subtitle="T-12 totals by category, largest first · click to trace" />
          <div className="p-4">
            <HorizontalBars data={expenses} onSelect={(k) => onTrace(k, "T12")} />
          </div>
        </Card>
        <Card>
          <CardHeader title="Profitability trend" subtitle="Monthly margins (each computed by the engine)" />
          <div className="px-3 pb-3 pt-3">
            <MultiLineChart
              data={series}
              series={[
                { key: "gross_margin", name: "Gross margin" },
                { key: "ebitda_margin", name: "EBITDA margin" },
                { key: "net_margin", name: "Net margin" },
              ]}
              height={300}
              onSelect={(p) => onTrace("ebitda_margin", p)}
            />
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Commentary workspaceId={workspaceId} modelVersion={version} />
        <Card>
          <CardHeader title="Model integrity" subtitle="Deterministic checks on this run" />
          <ul className="divide-y divide-ink-100 text-[13px]">
            <li className="flex items-center justify-between px-4 py-2.5">
              <span>Cross-foot checks</span>
              <StatusBadge kind={m.crossfoot.length && m.crossfoot.every((c) => c.passed) ? "VALID" : "INCOMPLETE"} size="xs" label={m.crossfoot.length ? `${m.crossfoot.filter((c) => c.passed).length}/${m.crossfoot.length} passed` : "Skipped"} />
            </li>
            <li className="flex items-center justify-between px-4 py-2.5">
              <span>Subtotal reconciliation breaks</span>
              <span className="num">{m.reconciliations.filter((r) => !r.matches).length}</span>
            </li>
            <li className="flex items-center justify-between px-4 py-2.5">
              <span>Incomplete monthly values</span>
              <span className="num">{data.incomplete.length}</span>
            </li>
            <li className="flex items-center justify-between px-4 py-2.5">
              <span>Open validation items</span>
              <StatusBadge kind={data.check_summary.overall} size="xs" label={`${data.check_summary.counts.REVIEW_REQUIRED} review · ${data.check_summary.counts.WARNING} warn`} />
            </li>
            <li className="px-4 py-2.5 text-xs text-ink-500">
              Window {periodLabel(m.window[0])} – {periodLabel(m.window[m.window.length - 1])} · engine <span className="font-mono">{m.engine}</span>
            </li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
