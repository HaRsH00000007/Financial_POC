import clsx from "clsx";
import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { Tooltip } from "@/components/Overlay";
import { formatOf, fmtValue, metricName, money, pct, periodLabel } from "@/lib/format";
import type { FinancialModel } from "@/types";

interface RowDef {
  key: string;
  kind: "source" | "derived" | "ratio";
  emphasis?: boolean;
  children?: string[];
  indent?: boolean;
}

export function T12Table({ model, onTrace, sourceHint }: { model: FinancialModel; onTrace: (metric: string, period: string) => void; sourceHint: (metric: string) => string }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ operating_expenses: false });
  const [showPrior, setShowPrior] = useState(false);
  const rows: RowDef[] = [
    { key: "revenue", kind: "source", emphasis: true },
    { key: "cogs", kind: "source" },
    { key: "gross_profit", kind: "derived", emphasis: true },
    { key: "gross_margin", kind: "ratio" },
    { key: "operating_expenses", kind: "derived", children: model.opex_components },
    { key: "ebitda", kind: "derived", emphasis: true },
    { key: "ebitda_margin", kind: "ratio" },
    { key: "depreciation", kind: "source" },
    { key: "interest", kind: "source" },
    { key: "taxes", kind: "source" },
    { key: "net_income", kind: "derived", emphasis: true },
    { key: "net_margin", kind: "ratio" },
  ];

  const flat: RowDef[] = [];
  rows.forEach((r) => {
    if (!(r.key in model.values)) {
      flat.push(r);
      return;
    }
    flat.push(r);
    if (r.children && expanded[r.key]) r.children.forEach((c) => flat.push({ key: c, kind: "source", indent: true }));
  });

  const win = model.window;
  const hasPrior = !!model.prior_window && Object.keys(model.prior_t12).length > 0;

  const cell = (metric: string, p: string) => {
    const v = model.values[metric]?.[p];
    const res = model.per_period[metric]?.[p];
    const fmt = formatOf(metric);
    if (v === undefined) return <span className="text-ink-300">n/r</span>;
    if (v === null) {
      return (
        <Tooltip content={res ? `INCOMPLETE — missing: ${res.missing_inputs.map(metricName).join(", ")}. Not estimated.` : "Missing in source — not estimated."}>
          <span className="inline-flex items-center gap-1 text-risk-700">
            <span className="h-1.5 w-1.5 rounded-full bg-risk-600" />—
          </span>
        </Tooltip>
      );
    }
    return <span className={clsx(v < 0 && "text-risk-700")}>{fmt === "percent" ? pct(v) : money(v)}</span>;
  };

  const total = (metric: string, which: "t12" | "prior_t12") => {
    const r = model[which][metric];
    if (!r) return <span className="text-ink-300">—</span>;
    if (r.result === null)
      return (
        <Tooltip content={`INCOMPLETE — ${r.missing_inputs.length} input(s) missing`}>
          <span className="text-[11px] font-semibold text-risk-700">INCOMPLETE</span>
        </Tooltip>
      );
    return fmtValue(r.result, formatOf(metric));
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink-100 px-4 py-2 text-xs text-ink-500">
        <span>
          USD · {periodLabel(win[0])} – {periodLabel(win[win.length - 1])} · click any number for its audit trail
        </span>
        {hasPrior && (
          <label className="inline-flex cursor-pointer items-center gap-1.5">
            <input type="checkbox" checked={showPrior} onChange={(e) => setShowPrior(e.target.checked)} className="accent-ink-900" />
            Show prior T-12 &amp; YoY
          </label>
        )}
      </div>
      <div className="scroll-thin overflow-x-auto">
        <table className="w-full border-separate border-spacing-0 text-[12.5px]">
          <thead>
            <tr className="text-[10.5px] uppercase tracking-wide text-ink-500">
              <th className="sticky left-0 z-20 min-w-[210px] border-b border-ink-200 bg-ink-50 px-4 py-2 text-left font-medium">Metric</th>
              <th className="border-b border-ink-200 bg-ink-50 px-2 py-2 text-left font-medium">Basis</th>
              {win.map((p, i) => (
                <th key={p} className="whitespace-nowrap border-b border-ink-200 bg-ink-50 px-3 py-2 text-right font-medium">
                  <div className="text-ink-400">M{i + 1}</div>
                  {periodLabel(p, true)}
                </th>
              ))}
              <th className="whitespace-nowrap border-b border-l border-ink-200 bg-ink-100 px-3 py-2 text-right font-semibold text-ink-700">T-12 Total</th>
              {showPrior && (
                <>
                  <th className="whitespace-nowrap border-b border-ink-200 bg-ink-50 px-3 py-2 text-right font-medium">Prior T-12</th>
                  <th className="whitespace-nowrap border-b border-ink-200 bg-ink-50 px-3 py-2 text-right font-medium">YoY</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {flat.map((r) => {
              const present = r.key in model.values;
              const ratio = r.kind === "ratio";
              const g = model.growth[r.key];
              return (
                <tr key={r.key} className={clsx("group", r.emphasis && "font-semibold", ratio && "text-ink-500")}>
                  <td
                    className={clsx(
                      "sticky left-0 z-10 border-b border-ink-100 px-4 py-2 group-hover:bg-ink-50",
                      r.emphasis ? "bg-white text-ink-950" : "bg-white",
                      ratio && "italic",
                    )}
                  >
                    <div className={clsx("flex items-center gap-1", r.indent && "pl-5 font-normal text-ink-600")}>
                      {r.children && r.children.length > 0 ? (
                        <button onClick={() => setExpanded((e) => ({ ...e, [r.key]: !e[r.key] }))} className="rounded p-0.5 text-ink-400 hover:bg-ink-100" aria-label="Expand components">
                          <ChevronRight className={clsx("h-3.5 w-3.5 transition-transform", expanded[r.key] && "rotate-90")} />
                        </button>
                      ) : (
                        !r.indent && <span className="w-[18px]" />
                      )}
                      {metricName(r.key)}
                    </div>
                  </td>
                  <td className="whitespace-nowrap border-b border-ink-100 px-2 py-2 font-mono text-[10.5px] font-normal not-italic text-ink-400 group-hover:bg-ink-50">
                    {!present ? "not reported" : r.kind === "source" ? sourceHint(r.key) : model.per_period[r.key]?.[win[0]]?.formula_id}
                  </td>
                  {win.map((p) => (
                    <td key={p} className="num whitespace-nowrap border-b border-ink-100 px-3 py-2 text-right group-hover:bg-ink-50">
                      {present ? (
                        <button className="rounded px-1 hover:bg-brand-50 hover:text-brand-700" onClick={() => onTrace(r.key, p)}>
                          {cell(r.key, p)}
                        </button>
                      ) : (
                        <span className="text-ink-300">n/r</span>
                      )}
                    </td>
                  ))}
                  <td className="num whitespace-nowrap border-b border-l border-ink-100 bg-ink-50/70 px-3 py-2 text-right group-hover:bg-ink-100">
                    {present ? (
                      <button className="rounded px-1 hover:bg-brand-50 hover:text-brand-700" onClick={() => onTrace(r.key, "T12")}>
                        {total(r.key, "t12")}
                      </button>
                    ) : (
                      <span className="text-ink-300">—</span>
                    )}
                  </td>
                  {showPrior && (
                    <>
                      <td className="num whitespace-nowrap border-b border-ink-100 px-3 py-2 text-right font-normal">
                        {present ? (
                          <button className="rounded px-1 hover:bg-brand-50" onClick={() => onTrace(r.key, "T12_PRIOR")}>
                            {total(r.key, "prior_t12")}
                          </button>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className={clsx("num whitespace-nowrap border-b border-ink-100 px-3 py-2 text-right font-normal", g?.result != null && (g.result >= 0 ? "text-ok-700" : "text-risk-700"))}>
                        {g ? (g.result === null ? "—" : pct(g.result, true)) : ""}
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1 px-4 py-2.5 text-[11px] text-ink-500">
        <span><span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-risk-600" />Incomplete — input missing, never estimated</span>
        <span>n/r — not reported in source</span>
        <span>Totals: <span className="font-mono">T12_001</span> (Σ 12 months); margins on T-12 totals</span>
      </div>
    </div>
  );
}
