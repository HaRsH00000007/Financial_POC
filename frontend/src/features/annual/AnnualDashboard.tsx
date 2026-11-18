import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/Button";
import { Card, CardHeader } from "@/components/Card";
import { HorizontalBars, MonthlyBarChart, MultiLineChart } from "@/components/FinancialChart";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge } from "@/components/StatusBadge";
import { currencyLabel, fmtValue, metricName, pct, periodLabel, valueFormat } from "@/lib/format";
import type { AnnualModelResponse } from "@/types";
import { AnnualInsights } from "./AnnualInsights";

const EXPENSES = ["materials_cost", "purchases_traded", "excise_duty", "employee_costs", "finance_costs", "depreciation", "other_expenses"];
const LEVERAGE = ["total_debt", "net_debt", "net_debt_to_ebitda", "debt_to_equity", "current_ratio", "interest_cover", "roe"];

export function AnnualDashboard({
  workspaceId,
  data,
  onTrace,
  stale,
  onRecalculate,
  recalculating,
}: {
  workspaceId: string;
  data: AnnualModelResponse;
  onTrace: (metric: string, period: string) => void;
  stale: boolean;
  onRecalculate: () => void;
  recalculating: boolean;
}) {
  const m = data.model;
  const L = m.latest;
  const r = (k: string, p = L) => m.per_period[k]?.[p] ?? null;
  const v = (k: string, p = L) => m.values[k]?.[p] ?? null;
  const series = m.periods.map((p) => ({
    period: p,
    revenue: v("revenue", p),
    ebitda: v("ebitda", p),
    profit: v("profit", p),
    ebitda_margin: v("ebitda_margin", p),
    net_margin: v("net_margin", p),
    roe: v("roe", p),
    cfo: v("cfo", p),
    capex: v("capex", p),
    fcf: v("fcf", p),
  }));
  const expenses = EXPENSES.filter((k) => v(k) !== null)
    .map((k) => ({ key: k, name: metricName(k), value: v(k) }))
    .sort((a, b) => (b.value ?? -1) - (a.value ?? -1));
  const growth = (k: string) => r(`${k}_growth`);
  const passed = m.identities.filter((i) => i.matches).length;
  const version = `${v("revenue")}-${v("profit")}-${data.check_summary.total}-${m.identities.length}`;

  const card = (k: string, label: string, sub?: string, formula?: string) => {
    const res = r(k);
    const g = growth(k);
    return (
      <MetricCard
        label={`${label} · ${periodLabel(L, true)}`}
        value={fmtValue(res?.result ?? v(k), valueFormat(k), true)}
        status={res?.status}
        sub={sub}
        delta={g?.result ?? undefined}
        deltaLabel={g?.result != null ? `${pct(g.result, true)} YoY` : undefined}
        formulaId={formula ?? res?.formula_id}
        onTrace={() => onTrace(k, L)}
      />
    );
  };

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

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {card("revenue", "Revenue")}
        {card("ebitda", "EBITDA", `${pct(v("ebitda_margin"))} margin`)}
        {card("profit", "Profit for the year", `${pct(v("net_margin"))} margin`)}
        {card("cfo", "Operating cash flow", `${pct(v("cash_conversion"))} of EBITDA`, "SOURCE")}
        {card("net_debt", "Net debt", `${fmtValue(v("net_debt_to_ebitda"), "multiple")} EBITDA`)}
        {card("roe", "Return on equity", "closing equity")}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Revenue from operations" subtitle="By fiscal year · click a bar to trace" />
          <div className="px-2 pb-3 pt-2">
            <MonthlyBarChart data={series} dataKey="revenue" name="Revenue" onSelect={(p) => onTrace("revenue", p)} />
          </div>
        </Card>
        <Card>
          <CardHeader title="EBITDA" subtitle="EBITDA_A01 = PBT + finance costs + D&A, per fiscal year" />
          <div className="px-2 pb-3 pt-2">
            <MonthlyBarChart data={series} dataKey="ebitda" name="EBITDA" onSelect={(p) => onTrace("ebitda", p)} />
          </div>
        </Card>
        <Card>
          <CardHeader title="Profitability & returns" subtitle="Margins on revenue from operations; ROE on closing equity" />
          <div className="px-3 pb-3 pt-3">
            <MultiLineChart
              data={series}
              series={[
                { key: "ebitda_margin", name: "EBITDA margin" },
                { key: "net_margin", name: "Net margin" },
                { key: "roe", name: "ROE" },
              ]}
              onSelect={(p) => onTrace("ebitda_margin", p)}
            />
          </div>
        </Card>
        <Card>
          <CardHeader title="Cash generation" subtitle="Operating cash flow, capex as printed (outflows negative) and free cash flow" />
          <div className="px-3 pb-3 pt-3">
            <MultiLineChart
              data={series}
              format="currency"
              series={[
                { key: "cfo", name: "Operating cash flow" },
                { key: "capex", name: "Capex (as printed)" },
                { key: "fcf", name: "Free cash flow" },
              ]}
              onSelect={(p) => onTrace("fcf", p)}
            />
          </div>
        </Card>
        <Card>
          <CardHeader title={`Expense breakdown · ${periodLabel(L, true)}`} subtitle="Statement of Profit and Loss lines, largest first · click to trace" />
          <div className="p-4">
            <HorizontalBars data={expenses} onSelect={(k) => onTrace(k, L)} />
          </div>
        </Card>
        <Card>
          <CardHeader title="Leverage & liquidity" subtitle="Balance-sheet ratios by fiscal year · click to trace" />
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="bg-ink-50 text-left text-[10.5px] uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Metric</th>
                  {m.periods.map((p) => (
                    <th key={p} className="px-2 py-2 text-right font-medium">{periodLabel(p, true)}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="num divide-y divide-ink-100">
                {LEVERAGE.map((k) => (
                  <tr key={k}>
                    <td className="px-4 py-2 font-sans text-ink-800">{metricName(k)}</td>
                    {m.periods.map((p) => (
                      <td key={p} className="px-2 py-2 text-right">
                        <button className="hover:text-brand-600 hover:underline" onClick={() => onTrace(k, p)}>
                          {fmtValue(v(k, p), valueFormat(k), true)}
                        </button>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <AnnualInsights workspaceId={workspaceId} modelVersion={version} />
        <Card>
          <CardHeader title="Model integrity" subtitle="Deterministic checks on this run" />
          <ul className="divide-y divide-ink-100 text-[13px]">
            <li className="flex items-center justify-between px-4 py-2.5">
              <span>Accounting identity checks</span>
              <StatusBadge kind={passed === m.identities.length ? "VALID" : "WARNING"} size="xs" label={`${passed}/${m.identities.length} reconcile`} />
            </li>
            <li className="flex items-center justify-between px-4 py-2.5">
              <span>Restated comparatives</span>
              <span className="num">{m.restatements.length}</span>
            </li>
            <li className="flex items-center justify-between px-4 py-2.5">
              <span>Incomplete / undefined values</span>
              <span className="num">{data.incomplete.length}</span>
            </li>
            <li className="flex items-center justify-between px-4 py-2.5">
              <span>Open validation items</span>
              <StatusBadge kind={data.check_summary.overall} size="xs" label={`${data.check_summary.counts.REVIEW_REQUIRED} review · ${data.check_summary.counts.WARNING} warn`} />
            </li>
            <li className="px-4 py-2.5 text-xs text-ink-500">
              {periodLabel(m.periods[0])} – {periodLabel(L)} · {currencyLabel()} · engine <span className="font-mono">{m.engine}</span>
            </li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
