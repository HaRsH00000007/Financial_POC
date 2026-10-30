import clsx from "clsx";
import { ArrowRight, Loader2, UserCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/Button";
import { Card, CardHeader } from "@/components/Card";
import { Callout } from "@/components/Feedback";
import { LayerTag, StatusBadge } from "@/components/StatusBadge";
import { useMeta } from "@/hooks/useMeta";
import { api } from "@/services/api";
import type { Category, Mapping, Workspace } from "@/types";
import { locationSummary } from "./ExtractionStep";

const METHOD: Record<Mapping["method"], { label: string; cls: string }> = {
  exact_synonym: { label: "Exact synonym", cls: "bg-ink-100 text-ink-700" },
  fuzzy_match: { label: "Fuzzy match", cls: "bg-warn-50 text-warn-700" },
  ai_suggested: { label: "AI suggested", cls: "bg-ai-50 text-ai-700" },
  user_override: { label: "Reviewer", cls: "bg-ok-50 text-ok-700" },
  unmapped: { label: "Unmapped", cls: "bg-risk-50 text-risk-700" },
};

const KIND_LABEL: Record<Category["kind"], string> = {
  input: "Income statement inputs (used in formulas)",
  reported_subtotal: "Reported subtotals (reconciliation only)",
  memo: "Balance-sheet memo (not used in P&L)",
  excluded: "Exclude",
};

export function CategorySelect({ value, onChange, disabled }: { value: string | null; onChange: (v: string | null) => void; disabled?: boolean }) {
  const { meta } = useMeta();
  const groups = useMemo(() => {
    const g: Record<string, Category[]> = {};
    (meta?.taxonomy ?? []).forEach((c) => (g[c.kind] ??= []).push(c));
    return g;
  }, [meta]);
  return (
    <select
      className={clsx("input h-8 py-0 pr-7 text-[13px]", !value && "border-risk-100 text-risk-700")}
      value={value ?? ""}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value || null)}
    >
      <option value="">— Unmapped —</option>
      {(Object.keys(KIND_LABEL) as Category["kind"][]).map((k) =>
        groups[k] ? (
          <optgroup key={k} label={KIND_LABEL[k]}>
            {groups[k].map((c) => (
              <option key={c.key} value={c.key}>
                {c.name}
              </option>
            ))}
          </optgroup>
        ) : null,
      )}
    </select>
  );
}

export function NormalizationStep({ ws, setWs, onNext }: { ws: Workspace; setWs: (w: Workspace) => void; onNext: () => void }) {
  const [filter, setFilter] = useState<"all" | "attention">("all");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { meta } = useMeta();
  const catName = (k: string | null) => meta?.taxonomy.find((c) => c.key === k)?.name ?? k ?? "—";

  const mappings = ws.rows.map((r) => ws.mappings[r.id]);
  const shown = filter === "all" ? mappings : mappings.filter((m) => m.status !== "VALID");
  const counts = mappings.reduce<Record<string, number>>((a, m) => ((a[m.method] = (a[m.method] ?? 0) + 1), a), {});

  const update = async (rowId: string, category: string | null) => {
    setPending(rowId);
    setError(null);
    try {
      setWs(await api.updateMappings(ws.id, [{ row_id: rowId, category }]));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setPending(null);
    }
  };

  const byCategory = useMemo(() => {
    const g: Record<string, string[]> = {};
    mappings.forEach((m) => m.category && (g[m.category] ??= []).push(m.raw_label));
    return g;
  }, [ws]);

  const needsAttention = mappings.filter((m) => m.status !== "VALID").length;

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
      <Card className="min-w-0">
        <CardHeader
          title="Normalization"
          subtitle="Map source labels onto the canonical chart of accounts. Rules run first; AI only suggests where rules cannot decide; reviewers have the final word."
          actions={
            <div className="flex items-center gap-2">
              <LayerTag layer="probabilistic" />
              <LayerTag layer="human" />
            </div>
          }
        />
        <div className="flex flex-wrap items-center gap-2 border-b border-ink-100 px-4 py-2">
          {(["all", "attention"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx("rounded-full px-2.5 py-1 text-xs font-medium", filter === f ? "bg-ink-950 text-white" : "bg-ink-100 text-ink-600 hover:bg-ink-200")}
            >
              {f === "all" ? `All rows (${mappings.length})` : `Needs attention (${needsAttention})`}
            </button>
          ))}
          <div className="ml-auto flex flex-wrap gap-1.5">
            {Object.entries(counts).map(([k, v]) => (
              <span key={k} className={clsx("rounded px-1.5 py-0.5 text-[11px] font-medium", METHOD[k as Mapping["method"]].cls)}>
                {v} {METHOD[k as Mapping["method"]].label.toLowerCase()}
              </span>
            ))}
          </div>
        </div>
        {error && <div className="px-4 pt-3"><Callout tone="warn">{error}</Callout></div>}
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full min-w-[760px] text-[13px]">
            <thead className="bg-ink-50 text-left text-[10.5px] uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2 font-medium">Source label</th>
                <th className="px-2 py-2 font-medium">Location</th>
                <th className="w-[240px] px-2 py-2 font-medium">Normalized category</th>
                <th className="px-2 py-2 font-medium">Method</th>
                <th className="px-2 py-2 text-right font-medium">Conf.</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {shown.map((m) => (
                <tr key={m.row_id} className={clsx("align-top hover:bg-ink-50/60", m.status === "REVIEW_REQUIRED" && "bg-risk-50/30")}>
                  <td className="px-4 py-2.5">
                    <div className="text-ink-900">{m.raw_label}</div>
                    <div className="mt-0.5 max-w-[320px] text-[11.5px] leading-snug text-ink-500">{m.rationale}</div>
                    {m.alternatives.length > 0 && m.method !== "exact_synonym" && m.method !== "user_override" && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {m.alternatives.slice(0, 3).map((a) => (
                          <button
                            key={a.category}
                            onClick={() => update(m.row_id, a.category)}
                            className="rounded border border-ink-200 bg-white px-1.5 py-0.5 text-[11px] text-ink-600 hover:border-brand-500 hover:text-brand-700"
                          >
                            {a.name} <span className="text-ink-400">{Math.round(a.score * 100)}%</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-2 py-2.5 font-mono text-[11.5px] text-ink-500">{locationSummary(ws, m.row_id)}</td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-1.5">
                      <CategorySelect value={m.category} onChange={(v) => update(m.row_id, v)} disabled={pending === m.row_id} />
                      {pending === m.row_id && <Loader2 className="h-3.5 w-3.5 animate-spin text-ink-400" />}
                    </div>
                  </td>
                  <td className="px-2 py-2.5">
                    <span className={clsx("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium", METHOD[m.method].cls)}>
                      {m.method === "user_override" && <UserCheck className="h-3 w-3" />}
                      {METHOD[m.method].label}
                    </span>
                  </td>
                  <td className="num px-2 py-2.5 text-right text-ink-600">{m.confidence ? `${Math.round(m.confidence * 100)}%` : "—"}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <StatusBadge kind={m.status} size="xs" />
                      {(m.method === "fuzzy_match" || m.method === "ai_suggested") && (
                        <button onClick={() => update(m.row_id, m.category)} className="text-[11px] font-medium text-brand-600 hover:underline">
                          Confirm
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <div className="space-y-4">
        <Card>
          <CardHeader title="Canonical categories" subtitle="Multiple source rows aggregate deterministically (AGG_001)" />
          <ul className="divide-y divide-ink-100">
            {Object.entries(byCategory).map(([k, labels]) => (
              <li key={k} className="px-4 py-2">
                <div className="flex items-center justify-between text-[13px]">
                  <span className="font-medium text-ink-900">{catName(k)}</span>
                  <span className="num text-xs text-ink-400">{labels.length} row{labels.length > 1 ? "s" : ""}</span>
                </div>
                <div className="mt-0.5 truncate text-[11.5px] text-ink-500">{labels.join(" + ")}</div>
              </li>
            ))}
          </ul>
        </Card>
        <Callout tone="brand">Every mapping change is written to the audit log with the previous value and method, then validation re-runs automatically.</Callout>
        <div className="flex justify-end">
          <Button variant="primary" onClick={onNext} iconRight={<ArrowRight className="h-4 w-4" />}>
            Continue to validation
          </Button>
        </div>
      </div>
    </div>
  );
}
