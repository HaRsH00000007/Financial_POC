import { Card, CardHeader } from "@/components/Card";
import { LayerStack, PipelineFlow, PlatformModules, Responsibilities } from "@/features/ArchitectureDiagram";

const CONTROLS = [
  ["LLMs never produce authoritative numbers", "Arithmetic lives only in the formula engine (Decimal, AST-parsed formulas). The AI layer receives verified outputs and tool results."],
  ["Numeric-claim guard", "Every figure in AI commentary and assistant answers is parsed and matched against engine values at its stated precision. Unverifiable drafts are replaced by a deterministic template."],
  ["No silent imputation", "Missing inputs propagate as INCOMPLETE through every dependent formula and T-12 total. Reviewers can supply a value only with a written justification, which is audited."],
  ["Rules before AI", "Normalization uses exact synonyms and fuzzy rules first; AI suggestions apply only to what rules cannot decide and are flagged WARNING until a reviewer confirms."],
  ["Independent reconciliation", "Subtotals printed in the source are never used as inputs; they are recomputed and reconciled, surfacing source errors (e.g. a transposed digit)."],
  ["Cross-foot checks", "Each P&L formula is re-applied to T-12 totals and compared with the sum of monthly results."],
  ["Tamper-evident audit log", "Every agent step, mapping change, resolution, calculation and AI output is written to a SHA-256 hash-chained log."],
  ["Cell-level lineage", "Every value carries document, page / sheet!cell, raw token, extraction method and confidence through aggregation and formulas."],
];

export function Architecture() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 lg:px-8">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink-950">Hybrid AI Architecture</h1>
        <p className="mt-1 max-w-3xl text-[13.5px] leading-relaxed text-ink-600">
          “AI can reason about financial information. Deterministic systems calculate the numbers. Every important result remains explainable and traceable.”
        </p>
      </div>
      <Card>
        <CardHeader title="Request flow" subtitle="User → AI / orchestration → extraction + normalization → deterministic engine → audit → AI insights" />
        <div className="p-4"><PipelineFlow /></div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Layers" />
          <div className="p-4"><LayerStack /></div>
        </Card>
        <Card>
          <CardHeader title="One platform, two modules" subtitle="Both modules share the LLM, agent and audit layers" />
          <div className="p-4"><PlatformModules /></div>
        </Card>
      </div>
      <div>
        <div className="label-caps mb-2">Separation of responsibilities</div>
        <Responsibilities />
      </div>
      <Card>
        <CardHeader title="Controls implemented in this POC" />
        <dl className="grid gap-px bg-ink-100 md:grid-cols-2">
          {CONTROLS.map(([t, d]) => (
            <div key={t} className="bg-white p-4">
              <dt className="text-[13px] font-semibold text-ink-950">{t}</dt>
              <dd className="mt-1 text-[12.5px] leading-relaxed text-ink-600">{d}</dd>
            </div>
          ))}
        </dl>
      </Card>
      <Card>
        <CardHeader title="Agent orchestration (Coordinator → Specialists)" />
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full min-w-[640px] text-[13px]">
            <thead className="bg-ink-50 text-left text-[10.5px] uppercase tracking-wide text-ink-500">
              <tr><th className="px-4 py-2 font-medium">Agent</th><th className="px-2 py-2 font-medium">Layer</th><th className="px-4 py-2 font-medium">Responsibility</th></tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {[
                ["Coordinator", "Orchestration", "Plans the workflow, records the plan, pauses for human review before calculation."],
                ["Ingestion Agent", "Probabilistic + rules", "Classifies the document (LLM when available) and extracts monthly tables with page/cell references."],
                ["Normalization Agent", "Probabilistic + rules", "Maps labels to the taxonomy; AI suggestions only for rows the rules cannot map."],
                ["Validation Agent", "Deterministic", "Coverage, gaps, missing values, duplicates, outliers, sign conventions, subtotal reconciliation."],
                ["Calculation Agent", "Deterministic", "Runs the formula registry. No LLM call exists in this code path."],
                ["Synthesis Agent", "Probabilistic", "Writes commentary from verified facts; output passes the numeric-claim guard."],
                ["Finance Assistant", "Probabilistic + tools", "Answers questions by calling deterministic tools (rank_months, explain_calculation, …)."],
              ].map(([a, l, r]) => (
                <tr key={a}><td className="px-4 py-2 font-medium text-ink-900">{a}</td><td className="px-2 py-2 text-xs text-ink-600">{l}</td><td className="px-4 py-2 text-ink-600">{r}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
