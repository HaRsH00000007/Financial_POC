import type { EvaluationState } from "@/types";

const e = (type: string, text: string, source = "") => ({
  id: Math.random().toString(36).slice(2, 10),
  type,
  text,
  source,
  created_at: new Date().toISOString(),
});

/** ILLUSTRATIVE EXAMPLE — fictional platforms and evidence, for demonstrating the framework only. */
export function exampleEvaluation(): EvaluationState {
  return {
    title: "AI Accounting Platform Evaluation — Illustrative Example",
    is_example: true,
    platforms: [
      { id: "a", name: "Platform A (fictional)" },
      { id: "b", name: "Platform B (fictional)" },
      { id: "c", name: "Platform C (fictional)" },
    ],
    weights: { financial_accuracy: 3, deterministic_calc: 3, auditability: 2, data_lineage: 2, security: 2 },
    cells: {
      "a:financial_accuracy": { assessment: "strong", entries: [e("test_result", "T-12 tie-out on 3 sample entities matched GL totals to the cent.", "Internal test log #12")] },
      "a:deterministic_calc": { assessment: "strong", entries: [e("documentation", "Architecture doc shows LLM limited to extraction; calc engine evaluates formulas.", "Vendor architecture whitepaper v2"), e("test_result", "Re-ran same file 3x; outputs byte-identical.", "Internal test log #13")] },
      "a:auditability": { assessment: "supported", entries: [e("evidence", "Audit log export includes user, timestamp and before/after values.")] },
      "a:data_lineage": { assessment: "supported", entries: [e("test_result", "EBITDA traced to PDF page and line in 4 clicks.")] },
      "a:integration": { assessment: "limited", entries: [e("limitation", "No native connector for our ERP; CSV import only.")] },
      "a:security": { assessment: "supported", entries: [e("documentation", "SOC 2 Type II report reviewed (period ending last quarter).", "Trust portal")] },
      "b:financial_accuracy": { assessment: "partial", entries: [e("test_result", "2 of 3 tie-outs matched; one variance traced to rounding in LLM-generated totals.")] },
      "b:deterministic_calc": { assessment: "limited", entries: [e("vendor_claim", "Vendor states calculations are 'AI-verified'."), e("limitation", "Could not confirm whether arithmetic is performed by the model.")] },
      "b:ai_capabilities": { assessment: "strong", entries: [e("test_result", "Extracted scanned PDFs with non-standard labels accurately in our sample.")] },
      "b:ux": { assessment: "strong", entries: [e("note", "Analysts completed the spreading task unaided in under 10 minutes.")] },
      "b:explainability": { assessment: "partial", entries: [e("vendor_claim", "Provides SHAP explanations for anomaly flags.")] },
      "c:governance": { assessment: "supported", entries: [e("documentation", "Model risk documentation aligned to SR 11-7 provided.")] },
      "c:human_in_loop": { assessment: "strong", entries: [e("test_result", "Low-confidence extractions routed to maker-checker queue.")] },
      "c:automation": { assessment: "partial", entries: [e("vendor_claim", "Claims 80% reduction in close time."), e("limitation", "No customer reference available to validate the claim.")] },
    },
  };
}

export function emptyEvaluation(): EvaluationState {
  return {
    title: "Enterprise AI Accounting Platform Evaluation",
    is_example: false,
    platforms: [
      { id: "a", name: "Platform A" },
      { id: "b", name: "Platform B" },
      { id: "c", name: "Platform C" },
    ],
    weights: {},
    cells: {},
  };
}
