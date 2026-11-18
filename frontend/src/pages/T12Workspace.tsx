import clsx from "clsx";
import { FilePlus2, MessageSquareText } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { AuditDrawer, type TraceTarget } from "@/components/AuditDrawer";
import { Button } from "@/components/Button";
import { Card, CardHeader } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/Feedback";
import { DependencyGraph } from "@/components/FormulaViewer";
import { Stepper, type Step } from "@/components/Stepper";
import { AnnualCalculationStep } from "@/features/annual/AnnualCalculationStep";
import { AnnualDashboard } from "@/features/annual/AnnualDashboard";
import { AnnualStatements } from "@/features/annual/AnnualStatements";
import { AnnualUpload } from "@/features/annual/AnnualUpload";
import { ContextPanel } from "@/features/annual/ContextPanel";
import { ANNUAL_SUGGESTIONS, AssistantPanel } from "@/features/t12/AssistantPanel";
import { AuditLogView } from "@/features/t12/AuditLogView";
import { CalculationStep } from "@/features/t12/CalculationStep";
import { Dashboard } from "@/features/t12/Dashboard";
import { DocumentCard, ExtractionStep } from "@/features/t12/ExtractionStep";
import { NormalizationStep } from "@/features/t12/NormalizationStep";
import { T12Table } from "@/features/t12/T12Table";
import { UploadStep } from "@/features/t12/UploadStep";
import { ValidationStep } from "@/features/t12/ValidationStep";
import { useMeta } from "@/hooks/useMeta";
import { setCurrency } from "@/lib/format";
import { api } from "@/services/api";
import type { AnnualModelResponse, ModelResponse, Workspace } from "@/types";

const STEPS: Step[] = [
  { key: "upload", label: "Upload" },
  { key: "extract", label: "AI Extraction", layer: "probabilistic" },
  { key: "normalize", label: "Normalization", layer: "human" },
  { key: "validate", label: "Validation", layer: "deterministic" },
  { key: "calculate", label: "Calculation", layer: "deterministic" },
  { key: "analyze", label: "Analysis & Audit", layer: "trust" },
];

type Tab = "overview" | "statement" | "graph" | "context" | "audit";
type Mode = "t12" | "annual";

export function T12Workspace() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const wsId = params.get("ws");
  const [mode, setMode] = useState<Mode>(location.pathname.startsWith("/annual") ? "annual" : "t12");
  const [ws, setWs] = useState<Workspace | null>(null);
  const [model, setModel] = useState<ModelResponse | null>(null);
  const [annualModel, setAnnualModel] = useState<AnnualModelResponse | null>(null);
  const [step, setStep] = useState(0);
  const [maxStep, setMaxStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [trace, setTrace] = useState<TraceTarget | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [assistant, setAssistant] = useState(false);
  const { meta } = useMeta();

  const annual = (ws?.kind ?? mode) === "annual";
  const hasModel = annual ? !!annualModel : !!model;
  setCurrency(annual ? { code: "INR", unit: ws?.unit ?? "crore" } : { code: "USD" });

  useEffect(() => {
    if (!ws) setMode(location.pathname.startsWith("/annual") ? "annual" : "t12");
  }, [location.pathname]);

  const go = (i: number) => {
    setStep(i);
    setMaxStep((m) => Math.max(m, i));
    window.scrollTo({ top: 0 });
  };

  // Restore a workspace from the URL (backend keeps state in memory).
  useEffect(() => {
    if (!wsId || ws?.id === wsId) return;
    setLoading(true);
    setError(null);
    api
      .workspace(wsId)
      .then(async (w) => {
        setWs(w);
        if (w.has_model) {
          if (w.kind === "annual") setAnnualModel(await api.annualModel(w.id));
          else setModel(await api.model(w.id));
          setStep(5);
          setMaxStep(5);
        } else {
          setStep(1);
          setMaxStep(3);
        }
      })
      .catch((e) => {
        setError(e.message);
        setParams({});
      })
      .finally(() => setLoading(false));
  }, [wsId]);

  const onReady = (w: Workspace) => {
    setWs(w);
    setModel(null);
    setAnnualModel(null);
    setParams({ ws: w.id });
    setMaxStep(3);
    go(1);
  };

  const updateWs = useCallback((w: Workspace) => setWs(w), []);

  const calculate = async () => {
    if (!ws) return;
    setCalculating(true);
    setError(null);
    try {
      if (ws.kind === "annual") setAnnualModel(await api.annualCalculate(ws.id));
      else setModel(await api.calculate(ws.id));
      setWs(await api.workspace(ws.id));
      if (step < 4) go(4);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCalculating(false);
    }
  };

  const reset = () => {
    setWs(null);
    setModel(null);
    setAnnualModel(null);
    setParams({});
    setStep(0);
    setMaxStep(0);
    setTab("overview");
    setAssistant(false);
  };

  const openTrace = (metric: string, period: string) => setTrace({ metric, period });

  const sourceHint = (metric: string) => {
    if (!ws) return "";
    const rows = ws.rows.filter((r) => ws.mappings[r.id]?.category === metric);
    if (!rows.length) return ws.resolutions.some((r) => r.category === metric) ? "attested" : "—";
    const pages = [...new Set(rows.flatMap((r) => Object.values(r.sources).map((s) => s.page)).filter(Boolean))] as number[];
    const prefix = rows.length > 1 ? `${rows.length} rows · ` : "";
    if (pages.length) return `${prefix}p.${Math.min(...pages)}–${Math.max(...pages)}`;
    return `${prefix}${Object.values(rows[0].sources)[0]?.sheet ?? "source"}`;
  };

  const stale = !!ws?.stale && hasModel;
  const tabs: [Tab, string][] = annual
    ? [
        ["overview", "Dashboard"],
        ["statement", "Financial Statements"],
        ["graph", "Formula Lineage"],
        ["context", "AI Context & Sources"],
        ["audit", "Audit Log"],
      ]
    : [
        ["overview", "Dashboard"],
        ["statement", "T-12 Statement"],
        ["graph", "Formula Lineage"],
        ["audit", "Audit Log"],
      ];

  return (
    <div className="flex">
      <div className="min-w-0 flex-1">
        {/* Workspace header */}
        <div className="border-b border-ink-200 bg-white">
          <div className="mx-auto max-w-[1440px] px-4 pt-4 lg:px-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="text-lg font-semibold tracking-tight text-ink-950">
                  {annual ? "Annual Report Analysis" : "Deterministic T-12 Financial Spreading"}
                </h1>
                <p className="text-[13px] text-ink-500">
                  {annual
                    ? "RAG-located statements · deterministic multi-year calculation · AI insights from a controlled brief"
                    : "AI-assisted extraction · deterministic calculation · source-level audit trail"}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {ws && hasModel && (
                  <Button variant={assistant ? "primary" : "ai"} onClick={() => setAssistant(!assistant)} icon={<MessageSquareText className="h-4 w-4" />}>
                    Ask AI
                  </Button>
                )}
                {ws && (
                  <Button onClick={reset} icon={<FilePlus2 className="h-4 w-4" />}>
                    {annual ? "New reports" : "New document"}
                  </Button>
                )}
              </div>
            </div>
            {ws && (
              <div className="mt-3">
                <DocumentCard ws={ws} />
              </div>
            )}
            {ws?.document.is_demo && (
              <div className="mt-3 inline-flex items-center gap-2 rounded-md border border-warn-100 bg-warn-50 px-2.5 py-1 text-[11.5px] font-semibold tracking-wide text-warn-700">
                DEMO DATA — Not for financial decision-making · Demo Dataset (fictional company)
              </div>
            )}
            <div className="mt-3 pb-2">
              <Stepper steps={STEPS} current={step} maxReached={hasModel ? 5 : ws ? maxStep : 0} onSelect={go} />
            </div>
          </div>
        </div>

        <div className="mx-auto max-w-[1440px] px-4 py-5 lg:px-6">
          {error && (
            <div className="mb-4">
              <ErrorState message={error} />
            </div>
          )}
          {loading && <Card><LoadingState lines={8} /></Card>}

          {!loading && step === 0 && (
            <div className="space-y-4">
              <div className="inline-flex rounded-md border border-ink-200 bg-white p-0.5" role="tablist" aria-label="Document type">
                {(
                  [
                    ["t12", "Monthly P&L (T-12)"],
                    ["annual", "Annual reports (multi-year, RAG)"],
                  ] as [Mode, string][]
                ).map(([k, l]) => (
                  <button
                    key={k}
                    role="tab"
                    aria-selected={mode === k}
                    onClick={() => setMode(k)}
                    className={clsx("rounded px-3 py-1.5 text-[13px] font-medium", mode === k ? "bg-ink-950 text-white" : "text-ink-600 hover:bg-ink-100")}
                  >
                    {l}
                  </button>
                ))}
              </div>
              {mode === "annual" ? <AnnualUpload onReady={onReady} /> : <UploadStep onReady={onReady} />}
            </div>
          )}
          {!loading && ws && step === 1 && <ExtractionStep ws={ws} onNext={() => go(2)} />}
          {!loading && ws && step === 2 && <NormalizationStep ws={ws} setWs={updateWs} onNext={() => go(3)} />}
          {!loading && ws && step === 3 && <ValidationStep ws={ws} setWs={updateWs} onCalculate={calculate} calculating={calculating} goNormalize={() => go(2)} />}
          {!loading && ws && step === 4 && !annual && model && <CalculationStep ws={ws} model={model} onNext={() => go(5)} />}
          {!loading && ws && step === 4 && annual && annualModel && <AnnualCalculationStep ws={ws} data={annualModel} onNext={() => go(5)} />}
          {!loading && ws && step === 4 && !hasModel && (
            <Card className="p-6 text-center text-[13px] text-ink-600">
              Run the calculation from the Validation step.
              <div className="mt-3">
                <Button variant="primary" onClick={calculate} loading={calculating}>Run deterministic calculation</Button>
              </div>
            </Card>
          )}
          {!loading && ws && step === 5 && hasModel && (
            <div>
              <div className="mb-4 flex gap-1 overflow-x-auto border-b border-ink-200">
                {tabs.map(([k, l]) => (
                  <button
                    key={k}
                    onClick={() => setTab(k)}
                    className={clsx(
                      "-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-[13px] font-medium transition-colors",
                      tab === k ? "border-ink-950 text-ink-950" : "border-transparent text-ink-500 hover:text-ink-900",
                    )}
                  >
                    {l}
                  </button>
                ))}
              </div>
              {tab === "overview" && !annual && model && (
                <Dashboard workspaceId={ws.id} data={model} onTrace={openTrace} stale={stale} onRecalculate={calculate} recalculating={calculating} />
              )}
              {tab === "overview" && annual && annualModel && (
                <AnnualDashboard workspaceId={ws.id} data={annualModel} onTrace={openTrace} stale={stale} onRecalculate={calculate} recalculating={calculating} />
              )}
              {tab === "statement" && !annual && model && (
                <Card>
                  <CardHeader title="T-12 Income Statement" subtitle={ws.entity ?? undefined} />
                  <T12Table model={model.model} onTrace={openTrace} sourceHint={sourceHint} />
                </Card>
              )}
              {tab === "statement" && annual && annualModel && <AnnualStatements data={annualModel} onTrace={openTrace} entity={ws.entity} />}
              {tab === "graph" && !annual && model && meta && (
                <Card>
                  <CardHeader
                    title="Formula dependency graph"
                    subtitle="Registered formulas evaluated in topological order. Values are T-12 results; hover to highlight lineage, click to open the audit trail."
                  />
                  <div className="p-4">
                    <DependencyGraph
                      nodes={meta.graph.nodes}
                      edges={meta.graph.edges}
                      values={Object.fromEntries(Object.entries(model.model.t12).map(([k, r]) => [k, { value: r.result, status: r.status }]))}
                      notReported={model.model.not_reported}
                      onSelect={(id) => openTrace(id, "T12")}
                    />
                  </div>
                </Card>
              )}
              {tab === "graph" && annual && annualModel && (
                <Card>
                  <CardHeader
                    title="Annual formula dependency graph"
                    subtitle={`Registered formulas evaluated in topological order for every fiscal year. Values shown for ${annualModel.model.latest}; click a node to open its audit trail.`}
                  />
                  <div className="p-4">
                    <DependencyGraph
                      nodes={annualModel.graph.nodes}
                      edges={annualModel.graph.edges}
                      values={Object.fromEntries(
                        Object.entries(annualModel.model.values).map(([k, s]) => [
                          k,
                          { value: s[annualModel.model.latest] ?? null, status: annualModel.model.per_period[k]?.[annualModel.model.latest]?.status ?? "DETERMINISTIC" },
                        ]),
                      )}
                      notReported={annualModel.model.not_reported}
                      onSelect={(id) => openTrace(id, annualModel.model.latest)}
                    />
                  </div>
                </Card>
              )}
              {tab === "context" && annual && <ContextPanel ws={ws} setWs={updateWs} />}
              {tab === "audit" && <AuditLogView workspaceId={ws.id} refreshKey={ws.agent_runs.length + ws.resolutions.length + (ws.external?.length ?? 0)} />}
            </div>
          )}
        </div>
      </div>

      {assistant && ws && hasModel && (
        <>
          <div className="fixed inset-0 z-30 bg-ink-950/30 xl:hidden" onClick={() => setAssistant(false)} />
          <aside className="fixed inset-y-0 right-0 z-40 w-full max-w-md border-l border-ink-200 shadow-pop xl:sticky xl:top-12 xl:z-0 xl:h-[calc(100vh-48px)] xl:w-[400px] xl:shadow-none">
            {annual ? (
              <AssistantPanel
                workspaceId={ws.id}
                onClose={() => setAssistant(false)}
                suggestions={ANNUAL_SUGGESTIONS}
                placeholder="Ask about the annual reports…"
                rag
              />
            ) : (
              <AssistantPanel workspaceId={ws.id} onClose={() => setAssistant(false)} />
            )}
          </aside>
        </>
      )}

      {ws && <AuditDrawer workspaceId={ws.id} target={trace} onClose={() => setTrace(null)} />}
    </div>
  );
}
