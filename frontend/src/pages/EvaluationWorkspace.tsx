import clsx from "clsx";
import { Download, FileText, FlaskConical, Info, Plus, Printer, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/Button";
import { Card, CardHeader } from "@/components/Card";
import { Callout, EmptyState, ErrorState, LoadingState } from "@/components/Feedback";
import { Drawer, Modal } from "@/components/Overlay";
import { exampleEvaluation, emptyEvaluation } from "@/features/evaluation/example";
import { ReportView } from "@/features/evaluation/ReportView";
import { api } from "@/services/api";
import type { EvalCell, EvalFramework, EvalSummary, EvaluationState } from "@/types";

const STORE_KEY = "fiw.evaluation.v1";
const LEVEL_STYLE: Record<string, string> = {
  not_assessed: "bg-white text-ink-400 ring-ink-200 border-dashed",
  not_supported: "bg-risk-50 text-risk-700 ring-risk-100",
  limited: "bg-warn-50 text-warn-700 ring-warn-100",
  partial: "bg-ink-100 text-ink-700 ring-ink-200",
  supported: "bg-brand-50 text-brand-700 ring-brand-100",
  strong: "bg-ok-50 text-ok-700 ring-ok-100",
};

function load(): EvaluationState {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* storage unavailable */
  }
  return emptyEvaluation();
}

type Tab = "matrix" | "summary" | "report";

export function EvaluationWorkspace() {
  const [fw, setFw] = useState<EvalFramework | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [state, setState] = useState<EvaluationState>(load);
  const [tab, setTab] = useState<Tab>("matrix");
  const [edit, setEdit] = useState<{ pid: string; dim: string } | null>(null);
  const [summary, setSummary] = useState<EvalSummary | null>(null);
  const [report, setReport] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);

  useEffect(() => {
    api.evalFramework().then(setFw, (e) => setError(e.message));
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(state));
    } catch {
      /* ignore */
    }
    const t = setTimeout(() => {
      api.evalSummary(state).then(setSummary, () => {});
    }, 250);
    return () => clearTimeout(t);
  }, [state]);

  useEffect(() => {
    if (tab === "report") {
      setReport(null);
      api.evalReport(state).then((r) => setReport(r.markdown), (e) => setError(e.message));
    }
  }, [tab]);

  const cell = (pid: string, dim: string): EvalCell => state.cells[`${pid}:${dim}`] ?? { assessment: "not_assessed", entries: [] };
  const setCell = (pid: string, dim: string, c: EvalCell) => setState((s) => ({ ...s, cells: { ...s.cells, [`${pid}:${dim}`]: c } }));
  const scaleLabel = useMemo(() => Object.fromEntries((fw?.scale ?? []).map((s) => [s.key, s.label])), [fw]);

  const addPlatform = () =>
    setState((s) => ({ ...s, platforms: [...s.platforms, { id: Math.random().toString(36).slice(2, 7), name: `Platform ${String.fromCharCode(65 + s.platforms.length)}` }] }));

  const download = () => {
    if (!report) return;
    const blob = new Blob([report], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "ai-accounting-evaluation.md";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  if (error && !fw) return <div className="p-6"><ErrorState message={error} /></div>;
  if (!fw) return <div className="p-6"><Card><LoadingState lines={8} /></Card></div>;

  const editing = edit ? fw.dimensions.find((d) => d.key === edit.dim) : null;
  const editingPlatform = edit ? state.platforms.find((p) => p.id === edit.pid) : null;

  return (
    <div>
      <div className="border-b border-ink-200 bg-white">
        <div className="mx-auto max-w-[1440px] px-4 pt-4 lg:px-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <input
                className="w-full max-w-2xl rounded border border-transparent bg-transparent px-1 -ml-1 text-lg font-semibold tracking-tight text-ink-950 hover:border-ink-200 focus:border-brand-500 focus:outline-none"
                value={state.title}
                onChange={(e) => setState((s) => ({ ...s, title: e.target.value }))}
                aria-label="Evaluation title"
              />
              <p className="text-[13px] text-ink-500">Structured, evidence-based comparison of enterprise AI accounting / FP&amp;A platforms</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={() => setState(exampleEvaluation())} icon={<FlaskConical className="h-4 w-4" />}>
                Load illustrative example
              </Button>
              <Button variant="ghost" onClick={() => setConfirmReset(true)} icon={<RotateCcw className="h-4 w-4" />}>
                Reset
              </Button>
            </div>
          </div>
          {state.is_example && (
            <div className="mt-3 inline-flex items-center gap-2 rounded-md border border-warn-100 bg-warn-50 px-2.5 py-1 text-[11.5px] font-semibold text-warn-700">
              ILLUSTRATIVE EXAMPLE — fictional platforms and evidence
            </div>
          )}
          <div className="mt-3 flex gap-1 overflow-x-auto">
            {(
              [
                ["matrix", "Assessment matrix"],
                ["summary", "Comparison summary"],
                ["report", "Evaluation report"],
              ] as [Tab, string][]
            ).map(([k, l]) => (
              <button
                key={k}
                onClick={() => setTab(k)}
                className={clsx("-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-[13px] font-medium", tab === k ? "border-ink-950 text-ink-950" : "border-transparent text-ink-500 hover:text-ink-900")}
              >
                {l}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1440px] space-y-4 px-4 py-5 lg:px-6">
        <Callout tone="neutral" icon={Info}>{fw.disclaimer}</Callout>

        {tab === "matrix" && (
          <Card>
            <CardHeader
              title="Assessment matrix"
              subtitle="Click a cell to record evidence, vendor claims, test results, documentation references and observed limitations."
              actions={<Button size="sm" onClick={addPlatform} icon={<Plus className="h-3.5 w-3.5" />}>Add platform</Button>}
            />
            <div className="scroll-thin overflow-x-auto">
              <table className="w-full min-w-[820px] border-separate border-spacing-0 text-[13px]">
                <thead>
                  <tr className="text-left text-[10.5px] uppercase tracking-wide text-ink-500">
                    <th className="sticky left-0 z-10 w-[300px] border-b border-ink-200 bg-ink-50 px-4 py-2 font-medium">Criterion</th>
                    <th className="w-20 border-b border-ink-200 bg-ink-50 px-2 py-2 font-medium">Weight</th>
                    {state.platforms.map((p) => (
                      <th key={p.id} className="min-w-[170px] border-b border-ink-200 bg-ink-50 px-2 py-1.5 font-medium">
                        <div className="flex items-center gap-1">
                          <input
                            className="w-full rounded border border-transparent bg-transparent px-1 py-0.5 text-[12px] font-semibold normal-case tracking-normal text-ink-900 hover:border-ink-200 focus:border-brand-500 focus:outline-none"
                            value={p.name}
                            onChange={(e) => setState((s) => ({ ...s, platforms: s.platforms.map((x) => (x.id === p.id ? { ...x, name: e.target.value } : x)) }))}
                            aria-label="Platform name"
                          />
                          {state.platforms.length > 1 && (
                            <button
                              className="rounded p-0.5 text-ink-300 hover:text-risk-600"
                              aria-label={`Remove ${p.name}`}
                              onClick={() => setState((s) => ({ ...s, platforms: s.platforms.filter((x) => x.id !== p.id) }))}
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          )}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {fw.dimensions.map((d, i) => (
                    <tr key={d.key} className="group">
                      <td className="sticky left-0 z-10 border-b border-ink-100 bg-white px-4 py-2.5 group-hover:bg-ink-50">
                        <div className="font-medium text-ink-900">
                          <span className="mr-1.5 text-ink-400">{i + 1}.</span>
                          {d.name}
                        </div>
                        <div className="text-[11.5px] leading-snug text-ink-500">{d.description}</div>
                      </td>
                      <td className="border-b border-ink-100 px-2 py-2.5 group-hover:bg-ink-50">
                        <select
                          className="input h-7 w-16 py-0 text-xs"
                          value={state.weights[d.key] ?? 1}
                          onChange={(e) => setState((s) => ({ ...s, weights: { ...s.weights, [d.key]: Number(e.target.value) } }))}
                          aria-label={`Weight for ${d.name}`}
                        >
                          {[0, 1, 2, 3].map((w) => (
                            <option key={w} value={w}>×{w}</option>
                          ))}
                        </select>
                      </td>
                      {state.platforms.map((p) => {
                        const c = cell(p.id, d.key);
                        const lims = c.entries.filter((x) => x.type === "limitation").length;
                        return (
                          <td key={p.id} className="border-b border-ink-100 px-2 py-2 group-hover:bg-ink-50">
                            <button
                              onClick={() => setEdit({ pid: p.id, dim: d.key })}
                              className={clsx("flex w-full items-center justify-between gap-2 rounded-md border px-2 py-1.5 text-left text-xs ring-1 ring-inset transition hover:shadow-card", LEVEL_STYLE[c.assessment], c.assessment !== "not_assessed" && "border-transparent")}
                            >
                              <span className="font-medium">{scaleLabel[c.assessment]}</span>
                              <span className="flex items-center gap-1.5 text-[10.5px] opacity-80">
                                {c.entries.length > 0 && <span>{c.entries.length} ev.</span>}
                                {lims > 0 && <span className="text-risk-700">{lims} lim.</span>}
                              </span>
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {tab === "summary" && (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {!summary && <Card><LoadingState /></Card>}
            {summary?.platforms.map((p) => (
              <Card key={p.platform_id}>
                <CardHeader title={p.name} subtitle={`${p.assessed}/${p.of} dimensions assessed · ${p.evidence_items} evidence items`} />
                <div className="p-4">
                  <div className="flex items-end justify-between">
                    <div>
                      <div className="label-caps">Weighted assessment index</div>
                      <div className="num mt-1 text-2xl font-semibold text-ink-950">{p.index === null ? "n/a" : `${Math.round(p.index * 100)} / 100`}</div>
                    </div>
                    <div className="text-right">
                      <div className="label-caps">Coverage</div>
                      <div className="num mt-1 text-[15px] font-semibold text-ink-700">{Math.round(p.coverage * 100)}%</div>
                    </div>
                  </div>
                  <div className="mt-2 h-1.5 rounded-full bg-ink-100">
                    <div className="h-1.5 rounded-full bg-brand-500" style={{ width: `${(p.index ?? 0) * 100}%` }} />
                  </div>
                  <p className="mt-1.5 text-[11px] text-ink-400">User-assigned; not an industry benchmark. Low coverage = low confidence in the index.</p>
                  {p.unsupported_claims > 0 && (
                    <Callout tone="warn" className="mt-3">
                      {p.unsupported_claims} vendor claim{p.unsupported_claims > 1 ? "s" : ""} without a supporting test or evidence.
                    </Callout>
                  )}
                  <div className="mt-4 grid gap-3">
                    <div>
                      <div className="label-caps mb-1 text-ok-700">Strengths</div>
                      {p.strengths.length ? <ul className="space-y-0.5 text-[12.5px] text-ink-700">{p.strengths.map((s) => <li key={s}>• {s}</li>)}</ul> : <p className="text-xs text-ink-400">None recorded</p>}
                    </div>
                    <div>
                      <div className="label-caps mb-1 text-risk-700">Limitations</div>
                      {p.limitations.length ? <ul className="space-y-0.5 text-[12.5px] text-ink-700">{p.limitations.map((s) => <li key={s}>• {s}</li>)}</ul> : <p className="text-xs text-ink-400">None recorded</p>}
                    </div>
                  </div>
                </div>
              </Card>
            ))}
            {summary && <p className="text-[11.5px] text-ink-500 md:col-span-2 xl:col-span-3">Method: {summary.method}</p>}
          </div>
        )}

        {tab === "report" && (
          <Card>
            <CardHeader
              icon={<FileText className="h-4 w-4" />}
              title="Evaluation report"
              subtitle="Generated deterministically from the recorded assessments and evidence"
              actions={
                <>
                  <Button size="sm" onClick={download} disabled={!report} icon={<Download className="h-3.5 w-3.5" />}>Markdown</Button>
                  <Button size="sm" onClick={() => window.print()} disabled={!report} icon={<Printer className="h-3.5 w-3.5" />}>Print / PDF</Button>
                </>
              }
            />
            <div className="p-6">
              {report ? (
                Object.keys(state.cells).length ? <ReportView markdown={report} /> : <EmptyState title="Nothing assessed yet" description="Record assessments in the matrix, or load the illustrative example." />
              ) : (
                <LoadingState lines={10} className="p-0" />
              )}
            </div>
          </Card>
        )}
      </div>

      <Drawer
        open={!!edit}
        onClose={() => setEdit(null)}
        title={editing?.name}
        subtitle={editingPlatform?.name}
        width="max-w-xl"
      >
        {edit && editing && (
          <CellEditor
            fw={fw}
            dimension={editing}
            cell={cell(edit.pid, edit.dim)}
            onChange={(c) => setCell(edit.pid, edit.dim, c)}
          />
        )}
      </Drawer>

      <Modal
        open={confirmReset}
        onClose={() => setConfirmReset(false)}
        title="Reset evaluation?"
        footer={
          <>
            <Button onClick={() => setConfirmReset(false)}>Cancel</Button>
            <Button variant="danger" onClick={() => { setState(emptyEvaluation()); setConfirmReset(false); }}>Reset</Button>
          </>
        }
      >
        <p className="text-[13px] text-ink-700">This clears all assessments and evidence stored in this browser.</p>
      </Modal>
    </div>
  );
}

function CellEditor({ fw, dimension, cell, onChange }: { fw: EvalFramework; dimension: EvalFramework["dimensions"][number]; cell: EvalCell; onChange: (c: EvalCell) => void }) {
  const [type, setType] = useState("evidence");
  const [text, setText] = useState("");
  const [source, setSource] = useState("");
  const typeLabel = Object.fromEntries(fw.evidence_types.map((t) => [t.key, t.label]));

  return (
    <div className="space-y-5 p-5">
      <p className="text-[13px] text-ink-600">{dimension.description}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-md border border-ink-200 p-3">
          <div className="label-caps mb-1.5">Guiding questions</div>
          <ul className="space-y-1 text-[12.5px] text-ink-700">{dimension.guiding_questions.map((q) => <li key={q}>• {q}</li>)}</ul>
        </div>
        <div className="rounded-md border border-ink-200 p-3">
          <div className="label-caps mb-1.5">Suggested tests</div>
          <ul className="space-y-1 text-[12.5px] text-ink-700">{dimension.suggested_tests.map((q) => <li key={q}>• {q}</li>)}</ul>
        </div>
      </div>

      <div>
        <div className="label-caps mb-2">Assessment</div>
        <div className="flex flex-wrap gap-1.5">
          {fw.scale.map((s) => (
            <button
              key={s.key}
              onClick={() => onChange({ ...cell, assessment: s.key })}
              className={clsx("rounded-md border px-2.5 py-1 text-xs font-medium ring-1 ring-inset", LEVEL_STYLE[s.key], cell.assessment === s.key ? "ring-2 ring-ink-900" : "opacity-80 hover:opacity-100")}
            >
              {s.label}
            </button>
          ))}
        </div>
        {cell.assessment !== "not_assessed" && cell.entries.length === 0 && (
          <Callout tone="warn" className="mt-2">An assessment without evidence is weak. Record what it is based on below.</Callout>
        )}
      </div>

      <div>
        <div className="label-caps mb-2">Evidence &amp; notes ({cell.entries.length})</div>
        <ul className="space-y-2">
          {cell.entries.map((e) => (
            <li key={e.id} className="flex items-start gap-2 rounded-md border border-ink-200 p-2.5">
              <span className={clsx("mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10.5px] font-semibold", e.type === "limitation" ? "bg-risk-50 text-risk-700" : e.type === "vendor_claim" ? "bg-warn-50 text-warn-700" : e.type === "test_result" ? "bg-ok-50 text-ok-700" : "bg-ink-100 text-ink-700")}>
                {typeLabel[e.type] ?? e.type}
              </span>
              <div className="min-w-0 flex-1 text-[13px] text-ink-800">
                {e.text}
                {e.source && <div className="text-[11.5px] text-ink-500">Source: {e.source}</div>}
              </div>
              <button className="rounded p-1 text-ink-400 hover:text-risk-600" onClick={() => onChange({ ...cell, entries: cell.entries.filter((x) => x.id !== e.id) })} aria-label="Remove">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-3 space-y-2 rounded-md border border-ink-200 bg-ink-50/60 p-3">
          <div className="grid gap-2 sm:grid-cols-[170px_1fr]">
            <select className="input" value={type} onChange={(e) => setType(e.target.value)}>
              {fw.evidence_types.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
            </select>
            <input className="input" placeholder="Source / reference (doc, URL, test ID)" value={source} onChange={(e) => setSource(e.target.value)} />
          </div>
          <textarea className="input min-h-[70px]" placeholder="What did you observe?" value={text} onChange={(e) => setText(e.target.value)} />
          <div className="flex justify-end">
            <Button
              variant="primary"
              size="sm"
              disabled={!text.trim()}
              icon={<Plus className="h-3.5 w-3.5" />}
              onClick={() => {
                onChange({ ...cell, entries: [...cell.entries, { id: Math.random().toString(36).slice(2, 10), type, text: text.trim(), source: source.trim(), created_at: new Date().toISOString() }] });
                setText("");
                setSource("");
              }}
            >
              Add entry
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
