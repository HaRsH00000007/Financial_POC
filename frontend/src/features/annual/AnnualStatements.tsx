import clsx from "clsx";
import { Fragment, useState, type ReactNode } from "react";
import { Card, CardHeader } from "@/components/Card";
import { currencyLabel, fmtValue, metricName, periodLabel, plain, valueFormat } from "@/lib/format";
import type { AnnualModelResponse, StatementLine } from "@/types";

const TABS = [
  ["income_statement", "Profit & Loss"],
  ["balance_sheet", "Balance Sheet"],
  ["cash_flow", "Cash Flow"],
  ["metrics", "Key metrics"],
] as const;

const METRICS: [string, string[]][] = [
  ["Profitability", ["total_income", "total_expenses", "pbt", "ebitda", "ebitda_margin", "ebitda_ex_oi", "profit", "net_margin", "effective_tax_rate", "interest_cover"]],
  ["Balance sheet", ["total_assets", "total_equity", "total_liabilities", "total_debt", "net_debt", "debt_to_equity", "net_debt_to_ebitda", "current_ratio", "roe"]],
  ["Cash flow", ["cfo", "cfi", "cff", "net_cash_change", "capex", "fcf", "cash_conversion"]],
  ["Growth (YoY)", ["revenue_growth", "ebitda_growth", "profit_growth", "cfo_growth"]],
];

export function AnnualStatements({ data, onTrace, entity }: { data: AnnualModelResponse; onTrace: (metric: string, period: string) => void; entity: string | null }) {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("income_statement");
  const periods = data.model.periods;

  return (
    <Card>
      <CardHeader
        title="Financial statements (consolidated)"
        subtitle={`${entity ?? ""} · ${currencyLabel()} · ${periodLabel(periods[0])} – ${periodLabel(periods[periods.length - 1])} · each year from the latest report that prints it · click a mapped figure for its audit trail`}
      />
      <div className="flex gap-1 overflow-x-auto border-b border-ink-100 px-3">
        {TABS.map(([k, l]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={clsx("-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-[13px] font-medium", tab === k ? "border-ink-950 text-ink-950" : "border-transparent text-ink-500 hover:text-ink-900")}
          >
            {l}
          </button>
        ))}
      </div>
      <div className="scroll-thin overflow-x-auto">
        {tab === "metrics" ? (
          <table className="w-full min-w-[640px] text-[13px]">
            <thead className="bg-ink-50 text-left text-[10.5px] uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2 font-medium">Metric (engine)</th>
                <th className="px-2 py-2 font-medium">Formula</th>
                {periods.map((p) => <th key={p} className="px-3 py-2 text-right font-medium">{periodLabel(p, true)}</th>)}
              </tr>
            </thead>
            <tbody>
              {METRICS.map(([group, keys]) => (
                <Group key={group} title={group} span={periods.length + 2}>
                  {keys.map((k) => (
                    <tr key={k} className="border-t border-ink-100 hover:bg-ink-50/60">
                      <td className="px-4 py-1.5 text-ink-900">{metricName(k)}</td>
                      <td className="px-2 py-1.5 font-mono text-[11px] text-ink-400">{Object.values(data.model.per_period[k] ?? {})[0]?.formula_id ?? "source"}</td>
                      {periods.map((p) => {
                        const res = data.model.per_period[k]?.[p];
                        const v = res ? res.result : data.model.values[k]?.[p];
                        return (
                          <td key={p} className="num px-3 py-1.5 text-right">
                            {res === undefined && v === undefined ? (
                              <span className="text-ink-300">—</span>
                            ) : (
                              <button onClick={() => onTrace(k, p)} className={clsx("hover:text-brand-600 hover:underline", v === null && "text-risk-700")}>
                                {v === null ? res?.status ?? "—" : fmtValue(v, valueFormat(k))}
                              </button>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </Group>
              ))}
            </tbody>
          </table>
        ) : (
          <StatementTable lines={data.statements[tab]} periods={periods} onTrace={onTrace} />
        )}
      </div>
    </Card>
  );
}

function Group({ title, span, children }: { title: string; span: number; children: ReactNode }) {
  return (
    <>
      <tr className="bg-ink-50/70">
        <td colSpan={span} className="px-4 py-1.5 text-[10.5px] font-semibold uppercase tracking-wide text-ink-500">{title}</td>
      </tr>
      {children}
    </>
  );
}

function StatementTable({ lines, periods, onTrace }: { lines: StatementLine[]; periods: string[]; onTrace: (metric: string, period: string) => void }) {
  let section = "";
  return (
    <table className="w-full min-w-[720px] text-[13px]">
      <thead className="bg-ink-50 text-left text-[10.5px] uppercase tracking-wide text-ink-500">
        <tr>
          <th className="px-4 py-2 font-medium">Line item (as printed)</th>
          <th className="px-2 py-2 font-medium">Note</th>
          {periods.map((p) => <th key={p} className="px-3 py-2 text-right font-medium">{periodLabel(p, true)}</th>)}
        </tr>
      </thead>
      <tbody>
        {lines.map((l) => {
          const header = l.section && l.section !== section ? l.section : null;
          section = l.section;
          const traceable = l.category && (l.kind === "input" || l.kind === "reported_subtotal");
          const total = /^(total|profit|net cash|net increase|closing)/i.test(l.label);
          return (
            <Fragment key={l.row_id}>
              {header && (
                <tr className="bg-ink-50/70">
                  <td colSpan={periods.length + 2} className="px-4 py-1.5 text-[10.5px] font-semibold uppercase tracking-wide text-ink-500">{header}</td>
                </tr>
              )}
              <tr className={clsx("border-t border-ink-100 hover:bg-ink-50/60", total && "font-semibold")}>
                <td className="px-4 py-1.5 text-ink-900">
                  {l.label}
                  {l.kind === "memo" && <span className="ml-1.5 text-[10.5px] font-normal text-ink-400">memo</span>}
                </td>
                <td className="px-2 py-1.5 font-mono text-[11px] text-ink-400">{l.note_ref ?? ""}</td>
                {periods.map((p) => {
                  const v = l.values[p];
                  if (v === undefined) return <td key={p} className="px-3 py-1.5 text-right text-ink-300">—</td>;
                  const txt = l.category === "eps_basic" || l.category === "eps_diluted" ? fmtValue(v, "number") : plain(v);
                  return (
                    <td key={p} className={clsx("num px-3 py-1.5 text-right", v !== null && v < 0 && "text-risk-700")} title={l.pages[p] ? `p.${l.pages[p]}` : undefined}>
                      {traceable ? (
                        <button onClick={() => onTrace(l.category!, p)} className="hover:text-brand-600 hover:underline">{txt}</button>
                      ) : (
                        txt
                      )}
                    </td>
                  );
                })}
              </tr>
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}
