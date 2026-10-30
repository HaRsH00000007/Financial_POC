import { ArrowRight, FileText, Sparkles } from "lucide-react";
import { Button } from "@/components/Button";
import { Card, CardHeader } from "@/components/Card";
import { Callout } from "@/components/Feedback";
import { LayerTag, StatusBadge } from "@/components/StatusBadge";
import { bytes, periodLabel } from "@/lib/format";
import type { Workspace } from "@/types";
import { AgentTimeline } from "./AgentTimeline";

export function locationSummary(ws: Workspace, rowId: string): string {
  const row = ws.rows.find((r) => r.id === rowId);
  if (!row) return "—";
  const srcs = Object.values(row.sources);
  const pages = [...new Set(srcs.map((s) => s.page).filter(Boolean))] as number[];
  if (pages.length) return pages.length > 1 ? `pp. ${Math.min(...pages)}–${Math.max(...pages)}` : `p. ${pages[0]}`;
  const first = srcs[0];
  if (first?.sheet) {
    const cells = srcs.map((s) => s.cell ?? "");
    return `${first.sheet}!${cells[0]}:${cells[cells.length - 1]}`;
  }
  if (first?.cell) return `${first.cell}…`;
  return "—";
}

export function DocumentCard({ ws }: { ws: Workspace }) {
  const d = ws.document;
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
      <div className="flex items-center gap-2">
        <FileText className="h-4 w-4 text-ink-500" />
        <span className="font-medium text-ink-900">{d.filename}</span>
        {d.is_demo && <span className="rounded bg-warn-50 px-1.5 py-0.5 text-[10.5px] font-semibold text-warn-700 ring-1 ring-warn-100">DEMO</span>}
      </div>
      <span className="text-ink-500">{d.file_type.toUpperCase()} · {bytes(d.size_bytes)}{d.pages ? ` · ${d.pages} pages` : ""}{d.sheets.length ? ` · ${d.sheets.length} sheets` : ""}</span>
      <span className="text-ink-500">
        Entity: <span className="text-ink-800">{ws.entity ?? "—"}</span>
      </span>
      <span className="font-mono text-[10.5px] text-ink-400" title={d.sha256}>sha256 {d.sha256.slice(0, 12)}…</span>
    </div>
  );
}

export function ExtractionStep({ ws, onNext }: { ws: Workspace; onNext: () => void }) {
  const periods = ws.periods;
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
      <Card className="min-w-0">
        <CardHeader
          title="AI Extraction"
          subtitle={`${ws.rows.length} line items across ${periods.length} monthly periods (${periods[0] ? periodLabel(periods[0]) : "—"} – ${periods.length ? periodLabel(periods[periods.length - 1]) : "—"})`}
          actions={<LayerTag layer="probabilistic" />}
        />
        <div className="border-b border-ink-100 px-4 py-2.5">
          <Callout tone="ai" icon={Sparkles}>
            Extraction <strong>interprets</strong> the document; it is not a source of truth for calculations. Every value keeps its page/cell reference and
            confidence, and nothing is calculated until mappings are normalized and validated.
            {ws.classification.document_type && (
              <span className="mt-1 block">
                Classified as <strong>{ws.classification.document_type}</strong> via {ws.classification.method}.
              </span>
            )}
          </Callout>
        </div>
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full min-w-[680px] text-[13px]">
            <thead className="bg-ink-50 text-left text-[10.5px] uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2 font-medium">#</th>
                <th className="px-2 py-2 font-medium">Source label (as extracted)</th>
                <th className="px-2 py-2 font-medium">Location</th>
                <th className="px-2 py-2 text-right font-medium">Values</th>
                <th className="px-2 py-2 text-right font-medium">Missing</th>
                <th className="px-2 py-2 font-medium">Confidence</th>
                <th className="px-4 py-2 font-medium">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {ws.rows.map((r) => {
                const vals = Object.values(r.values);
                const missing = periods.filter((p) => r.values[p] === null || r.values[p] === undefined).length;
                const conf = Object.values(r.sources).filter((s) => s.confidence > 0);
                const avg = conf.length ? conf.reduce((a, s) => Math.min(a, s.confidence), 1) : 0;
                return (
                  <tr key={r.id} className="hover:bg-ink-50/70">
                    <td className="px-4 py-2 font-mono text-[11px] text-ink-400">{r.id}</td>
                    <td className="px-2 py-2 text-ink-900">{r.label}</td>
                    <td className="px-2 py-2 font-mono text-[11.5px] text-ink-600">{locationSummary(ws, r.id)}</td>
                    <td className="num px-2 py-2 text-right text-ink-700">{vals.length - missing}</td>
                    <td className="num px-2 py-2 text-right">{missing ? <span className="font-medium text-risk-700">{missing}</span> : <span className="text-ink-400">0</span>}</td>
                    <td className="px-2 py-2">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-16 rounded-full bg-ink-100">
                          <div className={`h-1.5 rounded-full ${avg >= 0.9 ? "bg-ok-600" : avg >= 0.7 ? "bg-warn-600" : "bg-risk-600"}`} style={{ width: `${avg * 100}%` }} />
                        </div>
                        <span className="num text-[11.5px] text-ink-600">{Math.round(avg * 100)}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-2 text-xs text-ink-500">{r.notes.length ? r.notes[0] : r.sign_flipped ? "Sign convention normalized" : ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {!ws.rows.length && (
          <div className="p-4">
            <Callout tone="warn">No monthly line items were found. The extractor looks for a header row with at least two month columns (e.g. "Jan 2026").</Callout>
          </div>
        )}
      </Card>
      <div className="space-y-4">
        <Card>
          <CardHeader title="Agent activity" subtitle="Coordinator → specialists, recorded to the audit log" />
          <div className="p-4">
            <AgentTimeline runs={ws.agent_runs} />
          </div>
        </Card>
        <Card>
          <CardHeader title="Extraction log" />
          <ul className="space-y-1 p-4 font-mono text-[11.5px] text-ink-600">
            {ws.extraction_log.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </Card>
        <div className="flex items-center justify-between gap-3">
          <StatusBadge kind={ws.check_summary.overall as any} label={`${ws.check_summary.counts.REVIEW_REQUIRED} review · ${ws.check_summary.counts.WARNING} warnings`} />
          <Button variant="primary" onClick={onNext} iconRight={<ArrowRight className="h-4 w-4" />}>
            Review normalization
          </Button>
        </div>
      </div>
    </div>
  );
}
