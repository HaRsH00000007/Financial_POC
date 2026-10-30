import clsx from "clsx";
import { Calculator, ChevronDown, ShieldAlert, Trash2, UserCheck } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/Button";
import { Card, CardHeader } from "@/components/Card";
import { Callout } from "@/components/Feedback";
import { Modal } from "@/components/Overlay";
import { LayerTag, StatusBadge } from "@/components/StatusBadge";
import { money, periodLabel, plain } from "@/lib/format";
import { api } from "@/services/api";
import type { Status, ValidationCheck, Workspace } from "@/types";
import { CategorySelect } from "./NormalizationStep";

const ORDER: Status[] = ["REVIEW_REQUIRED", "WARNING", "VALID"];

export function ValidationStep({
  ws,
  setWs,
  onCalculate,
  calculating,
  goNormalize,
}: {
  ws: Workspace;
  setWs: (w: Workspace) => void;
  onCalculate: () => void;
  calculating: boolean;
  goNormalize: () => void;
}) {
  const [confirm, setConfirm] = useState(false);
  const [filter, setFilter] = useState<Status | "ALL">("ALL");
  const s = ws.check_summary;
  const open = ws.checks.filter((c) => c.status === "REVIEW_REQUIRED" && !c.resolved);
  const checks = [...ws.checks]
    .filter((c) => filter === "ALL" || c.status === filter)
    .sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status));

  const run = () => (open.length ? setConfirm(true) : onCalculate());

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
      <Card className="min-w-0">
        <CardHeader
          title="Validation"
          subtitle="Deterministic rules run before any calculation. Missing data is flagged — never invented."
          actions={<LayerTag layer="deterministic" />}
        />
        <div className="grid grid-cols-3 gap-px border-b border-ink-100 bg-ink-100">
          {(["VALID", "WARNING", "REVIEW_REQUIRED"] as Status[]).map((k) => (
            <button key={k} onClick={() => setFilter(filter === k ? "ALL" : k)} className={clsx("bg-white px-4 py-3 text-left transition", filter === k && "bg-ink-50")}>
              <StatusBadge kind={k} size="xs" />
              <div className="num mt-1.5 text-xl font-semibold text-ink-950">{s.counts[k]}</div>
            </button>
          ))}
        </div>
        <ul className="divide-y divide-ink-100">
          {checks.map((c) => (
            <CheckRow key={c.id} c={c} ws={ws} setWs={setWs} goNormalize={goNormalize} />
          ))}
        </ul>
      </Card>

      <div className="space-y-4">
        <Card>
          <CardHeader title="Reviewer resolutions" subtitle="Audited, with mandatory justification" icon={<UserCheck className="h-4 w-4" />} />
          {ws.resolutions.length === 0 ? (
            <p className="px-4 py-4 text-xs text-ink-500">None yet. Resolve review items on the left.</p>
          ) : (
            <ul className="divide-y divide-ink-100">
              {ws.resolutions.map((r) => (
                <li key={r.id} className="flex items-start gap-2 px-4 py-2.5 text-xs">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-ink-900">
                      {r.type === "value"
                        ? `${ws.rows.find((x) => x.id === r.row_id)?.label} · ${periodLabel(r.period!)} = ${money(r.value)}`
                        : `${r.category} attested as zero`}
                    </div>
                    <div className="text-ink-500">“{r.note}”</div>
                  </div>
                  <button
                    className="rounded p-1 text-ink-400 hover:bg-risk-50 hover:text-risk-700"
                    aria-label="Withdraw resolution"
                    onClick={async () => setWs(await api.removeResolution(ws.id, r.id))}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-2 text-[13px] font-semibold text-ink-950">
            <Calculator className="h-4 w-4 text-brand-600" /> Deterministic calculation
          </div>
          <p className="mt-1.5 text-xs leading-relaxed text-ink-600">
            Runs the formula registry over normalized inputs with exact decimal arithmetic. No language model is involved. Metrics that depend on missing
            inputs are reported as <strong>INCOMPLETE</strong>.
          </p>
          {open.length > 0 && (
            <Callout tone="warn" icon={ShieldAlert} className="mt-3">
              {open.length} item{open.length > 1 ? "s" : ""} still require review.
            </Callout>
          )}
          <Button variant="primary" size="lg" className="mt-3 w-full" onClick={run} loading={calculating} icon={<Calculator className="h-4 w-4" />}>
            Run deterministic calculation
          </Button>
        </Card>
      </div>

      <Modal
        open={confirm}
        onClose={() => setConfirm(false)}
        title="Proceed with unresolved review items?"
        footer={
          <>
            <Button onClick={() => setConfirm(false)}>Go back and review</Button>
            <Button
              variant="primary"
              onClick={() => {
                setConfirm(false);
                onCalculate();
              }}
            >
              Calculate anyway
            </Button>
          </>
        }
      >
        <p className="text-[13px] text-ink-700">
          {open.length} item{open.length > 1 ? "s" : ""} are marked REVIEW REQUIRED. The engine will still run, but any metric that depends on a missing or unmapped
          input will be shown as <strong>INCOMPLETE</strong> — it will not be estimated.
        </p>
        <ul className="mt-3 space-y-1 text-xs text-ink-600">
          {open.slice(0, 6).map((c) => (
            <li key={c.id}>• {c.title}</li>
          ))}
        </ul>
      </Modal>
    </div>
  );
}

function CheckRow({ c, ws, setWs, goNormalize }: { c: ValidationCheck; ws: Workspace; setWs: (w: Workspace) => void; goNormalize: () => void }) {
  const [expanded, setExpanded] = useState(c.status === "REVIEW_REQUIRED");
  const [value, setValue] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const act = async (fn: () => Promise<Workspace>) => {
    setBusy(true);
    setErr(null);
    try {
      setWs(await fn());
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const row = c.row_id ? ws.rows.find((r) => r.id === c.row_id) : null;
  const neighbours =
    row && c.period
      ? (() => {
          const i = ws.periods.indexOf(c.period);
          return [ws.periods[i - 1], ws.periods[i + 1]].filter(Boolean).map((p) => ({ p, v: row.effective_values[p] }));
        })()
      : [];
  const hasBody = c.detail || c.evidence?.length || c.resolvable;

  return (
    <li className="px-4 py-3">
      <button className="flex w-full items-start gap-3 text-left" onClick={() => hasBody && setExpanded(!expanded)}>
        <StatusBadge kind={c.status} size="xs" className="mt-0.5" />
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-medium text-ink-900">{c.title}</div>
          {!expanded && <div className="truncate text-xs text-ink-500">{c.detail}</div>}
        </div>
        <span className="hidden font-mono text-[10.5px] text-ink-400 sm:inline">{c.check}</span>
        {hasBody && <ChevronDown className={clsx("h-4 w-4 shrink-0 text-ink-400 transition-transform", expanded && "rotate-180")} />}
      </button>
      {expanded && (
        <div className="ml-[88px] mt-2 space-y-2 max-sm:ml-0">
          <p className="text-xs leading-relaxed text-ink-600">{c.detail}</p>
          {c.check === "reconciliation" && c.evidence.length > 0 && (
            <div className="overflow-x-auto rounded-md border border-ink-200">
              <table className="w-full text-xs">
                <thead className="bg-ink-50 text-left text-[10.5px] uppercase text-ink-500">
                  <tr>
                    <th className="px-2 py-1 font-medium">Period</th>
                    <th className="px-2 py-1 text-right font-medium">Printed in source</th>
                    <th className="px-2 py-1 text-right font-medium">Engine recomputed</th>
                    <th className="px-2 py-1 text-right font-medium">Variance</th>
                  </tr>
                </thead>
                <tbody className="num divide-y divide-ink-100">
                  {c.evidence.slice(0, 12).map((e: any) => (
                    <tr key={e.period}>
                      <td className="px-2 py-1">{periodLabel(e.period)}</td>
                      <td className="px-2 py-1 text-right">{plain(e.reported)}</td>
                      <td className="px-2 py-1 text-right">{plain(e.computed)}</td>
                      <td className="px-2 py-1 text-right font-medium text-warn-700">{plain(e.variance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {c.check === "missing_value" && c.resolvable && (
            <div className="rounded-md border border-ink-200 bg-ink-50/60 p-3">
              {neighbours.length > 0 && (
                <div className="mb-2 text-[11.5px] text-ink-500">
                  Context (not used for imputation): {neighbours.map((n) => `${periodLabel(n.p)} ${money(n.v)}`).join(" · ")}
                </div>
              )}
              <div className="grid gap-2 sm:grid-cols-[140px_1fr_auto]">
                <input className="input num" placeholder="Reviewed value" inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} />
                <input className="input" placeholder="Justification (required), e.g. tied to GL / invoice ref" value={note} onChange={(e) => setNote(e.target.value)} />
                <Button
                  variant="primary"
                  loading={busy}
                  disabled={!value || !note.trim() || isNaN(Number(value.replace(/,/g, "")))}
                  onClick={() =>
                    act(() => api.addResolution(ws.id, { type: "value", row_id: c.row_id, period: c.period, value: Number(value.replace(/,/g, "")), note }))
                  }
                >
                  Apply
                </Button>
              </div>
              <p className="mt-1.5 text-[11px] text-ink-500">Or leave it missing — dependent metrics for {periodLabel(c.period!)} will be INCOMPLETE.</p>
            </div>
          )}

          {c.check === "unmapped" && c.row_id && (
            <div className="flex flex-wrap items-center gap-2">
              <div className="w-64">
                <CategorySelect value={null} onChange={(v) => act(() => api.updateMappings(ws.id, [{ row_id: c.row_id!, category: v }]))} disabled={busy} />
              </div>
              <Button size="sm" variant="ghost" onClick={goNormalize}>
                Open in Normalization
              </Button>
            </div>
          )}

          {c.check === "mapping_confidence" && c.row_id && (
            <Button size="sm" loading={busy} onClick={() => act(() => api.updateMappings(ws.id, [{ row_id: c.row_id!, category: c.category }]))} icon={<UserCheck className="h-3.5 w-3.5" />}>
              Confirm mapping
            </Button>
          )}

          {c.check === "duplicate" && c.row_id && (
            <Button size="sm" loading={busy} onClick={() => act(() => api.updateMappings(ws.id, [{ row_id: c.row_id!, category: "excluded" }]))}>
              Exclude this row
            </Button>
          )}

          {c.check === "required_category" && c.resolvable && c.category && (
            <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
              <input className="input" placeholder="Justification (required), e.g. entity has no debt" value={note} onChange={(e) => setNote(e.target.value)} />
              <Button loading={busy} disabled={!note.trim()} onClick={() => act(() => api.addResolution(ws.id, { type: "category_zero", category: c.category, note }))}>
                Attest zero for all periods
              </Button>
            </div>
          )}
          {err && <p className="text-xs text-risk-700">{err}</p>}
        </div>
      )}
    </li>
  );
}
