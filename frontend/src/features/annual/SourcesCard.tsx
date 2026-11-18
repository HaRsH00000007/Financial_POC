import { Database, FileText } from "lucide-react";
import { Card, CardHeader } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { periodLabel } from "@/lib/format";
import type { Workspace } from "@/types";

const LABEL: Record<string, string> = {
  income_statement: "Profit & Loss",
  balance_sheet: "Balance Sheet",
  cash_flow: "Cash Flow",
};

/** Which report pages the statements were read from, and the retrieval index built over all pages. */
export function SourcesCard({ ws }: { ws: Workspace }) {
  return (
    <Card>
      <CardHeader icon={<FileText className="h-4 w-4" />} title="Statements located" subtitle="Structural markers + BM25 rank · consolidated preferred" />
      <ul className="divide-y divide-ink-100">
        {(ws.documents ?? []).map((d) => (
          <li key={d.id} className="px-4 py-2.5">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-[13px] font-medium text-ink-900" title={d.filename}>
                <span className="mr-1.5 font-mono text-[11px] text-ink-400">{d.id}</span>
                {d.filename}
              </span>
              <span className="shrink-0 text-[11px] text-ink-500">
                {d.fiscal_years.map((p) => periodLabel(p, true)).join(", ")} · {d.pages} pp
              </span>
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {Object.entries(LABEL).map(([k, l]) => {
                const s = d.statements[k];
                return s ? (
                  <span key={k} title={`${s.method} · scope ${s.scope} · BM25 rank ${s.bm25_rank ?? "-"} · candidates ${s.candidates.join(", ")}`}>
                    <StatusBadge kind={s.score >= 1 ? "VALID" : "WARNING"} size="xs" label={`${l} p.${s.page}`} />
                  </span>
                ) : (
                  <StatusBadge key={k} kind="REVIEW_REQUIRED" size="xs" label={`${l} not found`} />
                );
              })}
            </div>
          </li>
        ))}
      </ul>
      {ws.index && (
        <div className="flex items-center gap-2 border-t border-ink-100 px-4 py-2.5 text-xs text-ink-500">
          <Database className="h-3.5 w-3.5" />
          RAG index: {ws.index.chunks.toLocaleString()} chunks · {ws.index.vocabulary.toLocaleString()} terms · {ws.index.retriever}
        </div>
      )}
    </Card>
  );
}
