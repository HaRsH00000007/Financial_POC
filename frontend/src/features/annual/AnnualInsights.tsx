import { RefreshCw, ShieldCheck, ShieldX, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/Button";
import { Card, CardHeader } from "@/components/Card";
import { Callout, ErrorState, LoadingState } from "@/components/Feedback";
import { Tooltip } from "@/components/Overlay";
import { LayerTag } from "@/components/StatusBadge";
import { api } from "@/services/api";
import type { Commentary, InsightBrief } from "@/types";

function refText(brief: InsightBrief | undefined, id: string): string {
  if (!brief) return id;
  const f = brief.facts.find((x) => x.id === id);
  if (f) return `${f.name} (${f.period}): ${f.display} · ${f.formula_id ?? "source"}`;
  const q = brief.quality.find((x) => x.id === id);
  if (q) return q.text;
  const n = brief.narrative.find((x) => x.id === id);
  if (n) return `${n.document}, p.${n.page}: ${n.text.slice(0, 220)}…`;
  const e = brief.external.find((x) => x.id === id);
  if (e) return `${e.source}${e.as_of ? ` (${e.as_of})` : ""}: ${e.text}`;
  return id;
}

const REF_TONE: Record<string, string> = {
  F: "bg-brand-50 text-brand-700 ring-brand-100",
  Q: "bg-ok-50 text-ok-700 ring-ok-100",
  N: "bg-ai-50 text-ai-700 ring-ai-100",
  X: "bg-warn-50 text-warn-700 ring-warn-100",
};

/** AI insights written from the Insight Brief only; every figure is checked against the brief. */
export function AnnualInsights({ workspaceId, modelVersion }: { workspaceId: string; modelVersion: string }) {
  const [data, setData] = useState<Commentary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [narrative, setNarrative] = useState(true);

  const generate = async (withNarrative = narrative) => {
    setBusy(true);
    setError(null);
    try {
      setData(await api.insights(workspaceId, withNarrative));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const lastKey = useRef<string | null>(null);
  useEffect(() => {
    const key = `${workspaceId}:${modelVersion}`;
    if (lastKey.current === key) return;
    lastKey.current = key;
    setData(null);
    generate();
  }, [workspaceId, modelVersion]);

  const comp = data?.brief?.composition;
  return (
    <Card className="border-ai-100">
      <CardHeader
        icon={<Sparkles className="h-4 w-4 text-ai-600" />}
        title="AI insights"
        subtitle="Written from the Insight Brief only — engine figures, retrieved passages and external context. Never the full report."
        actions={
          <>
            <LayerTag layer="probabilistic" />
            <Button size="sm" variant="ghost" onClick={() => generate()} loading={busy} icon={<RefreshCw className="h-3.5 w-3.5" />}>
              Regenerate
            </Button>
          </>
        }
      />
      <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 px-4 py-2 text-xs text-ink-600">
        <label className="inline-flex cursor-pointer items-center gap-2">
          <input
            type="checkbox"
            checked={narrative}
            onChange={(e) => {
              setNarrative(e.target.checked);
              generate(e.target.checked);
            }}
          />
          Include retrieved management passages in the brief
        </label>
        {comp && (
          <span className="ml-auto text-ink-500">
            Brief: {comp.facts} engine facts · {comp.narrative_passages} passages from {comp.report_pages_in_brief} of {comp.report_pages_total} pages · {comp.external} external
          </span>
        )}
      </div>
      <div className="p-4">
        {error && <ErrorState message={error} onRetry={() => generate()} />}
        {!data && !error && <LoadingState lines={4} className="p-0" />}
        {data && (
          <>
            <ul className="space-y-3">
              {(data.insights ?? []).map((ins, i) => (
                <li key={i}>
                  <div className="text-[12.5px] font-semibold text-ink-950">{ins.title}</div>
                  <p className="mt-0.5 text-[13.5px] leading-relaxed text-ink-800">{ins.text}</p>
                  {ins.refs.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {ins.refs.map((r) => (
                        <Tooltip key={r} content={refText(data.brief, r)}>
                          <span className={`rounded px-1.5 py-0.5 font-mono text-[10.5px] ring-1 ring-inset ${REF_TONE[r[0]] ?? REF_TONE.F}`}>{r}</span>
                        </Tooltip>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ul>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-[11.5px]">
              <Tooltip content={data.numeric_check.passed ? "Every figure in the insights appears verbatim in the Insight Brief." : `Unverified: ${data.numeric_check.unverified.join(", ")}`}>
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium ring-1 ring-inset ${data.numeric_check.passed ? "bg-ok-50 text-ok-700 ring-ok-100" : "bg-risk-50 text-risk-700 ring-risk-100"}`}
                >
                  {data.numeric_check.passed ? <ShieldCheck className="h-3.5 w-3.5" /> : <ShieldX className="h-3.5 w-3.5" />}
                  {data.numeric_check.verified}/{data.numeric_check.checked} figures verified against the brief
                </span>
              </Tooltip>
              <span className="text-ink-500">Source: {data.source}</span>
              <span className="text-ink-400">· F = engine fact · Q = data quality · N = report passage · X = external</span>
            </div>
            {data.note && <Callout tone="warn" className="mt-2">{data.note}</Callout>}
            <p className="mt-3 border-t border-ink-100 pt-2 text-[11.5px] text-ink-500">{data.disclaimer}</p>
          </>
        )}
      </div>
    </Card>
  );
}
