export type Status = "VALID" | "WARNING" | "REVIEW_REQUIRED";
export type CalcStatus = "DETERMINISTIC" | "INCOMPLETE" | "UNDEFINED";

export interface SourceReference {
  document_id: string;
  document_name: string;
  page: number | null;
  sheet: string | null;
  cell: string | null;
  row_label: string;
  raw_text: string | null;
  extraction_method: string;
  confidence: number;
}

export interface RawRow {
  id: string;
  label: string;
  values: Record<string, number | null>;
  effective_values: Record<string, number | null>;
  sources: Record<string, SourceReference>;
  confidence: number;
  notes: string[];
  sign_flipped: boolean;
}

export interface Mapping {
  row_id: string;
  raw_label: string;
  category: string | null;
  method: "exact_synonym" | "fuzzy_match" | "ai_suggested" | "user_override" | "unmapped";
  confidence: number;
  status: Status;
  rationale: string;
  alternatives: { category: string; name: string; score: number }[];
}

export interface ValidationCheck {
  id: string;
  check: string;
  status: Status;
  title: string;
  detail: string;
  row_id: string | null;
  category: string | null;
  period: string | null;
  resolvable: boolean;
  resolved: boolean;
  evidence: Record<string, unknown>[];
}

export interface AgentRun {
  id: string;
  agent: string;
  layer: "orchestration" | "probabilistic" | "deterministic";
  action: string;
  status: "running" | "completed" | "error";
  started_at: string;
  finished_at?: string;
  duration_ms?: number;
  outputs: Record<string, unknown>;
  error?: string;
}

export interface Resolution {
  id: string;
  type: "value" | "category_zero";
  note: string;
  row_id: string | null;
  period: string | null;
  value: number | null;
  category: string | null;
}

export interface LLMInfo {
  name: string;
  model: string;
  live: boolean;
}

export interface CheckSummary {
  counts: Record<Status, number>;
  overall: Status;
  total: number;
}

export interface Workspace {
  id: string;
  stage: "extracted" | "normalized" | "validated" | "calculated";
  stale: boolean;
  document: {
    id: string;
    filename: string;
    file_type: "pdf" | "xlsx" | "csv";
    size_bytes: number;
    sha256: string;
    uploaded_at: string;
    is_demo: boolean;
    pages: number | null;
    sheets: string[];
  };
  classification: { document_type?: string; method?: string; confidence?: number | null };
  entity: string | null;
  periods: string[];
  scale: number;
  extraction_log: string[];
  rows: RawRow[];
  mappings: Record<string, Mapping>;
  resolutions: Resolution[];
  checks: ValidationCheck[];
  check_summary: CheckSummary;
  categories_present: string[];
  agent_runs: AgentRun[];
  has_model: boolean;
  llm: LLMInfo;
}

export interface CalcInput {
  name: string;
  value: number | null;
  kind: "source" | "derived";
}

export interface CalculationResult {
  metric: string;
  period: string;
  formula_id: string;
  expression: string;
  substituted: string;
  inputs: CalcInput[];
  result: number | null;
  status: CalcStatus;
  missing_inputs: string[];
  engine: string;
}

export interface FinancialModel {
  engine: string;
  periods: string[];
  window: string[];
  window_complete: boolean;
  prior_window: string[] | null;
  opex_components: string[];
  not_reported: string[];
  values: Record<string, Record<string, number | null>>;
  per_period: Record<string, Record<string, CalculationResult>>;
  t12: Record<string, CalculationResult>;
  prior_t12: Record<string, CalculationResult>;
  growth: Record<string, CalculationResult>;
  reconciliations: {
    metric: string;
    reported_category: string;
    period: string;
    reported: number;
    computed: number;
    variance: number;
    matches: boolean;
  }[];
  crossfoot: { metric: string; sum_of_months: number; formula_on_totals: number; difference: number; passed: boolean }[];
}

export interface ModelResponse {
  model: FinancialModel;
  incomplete: { metric: string; period: string; status: CalcStatus; missing: string[] }[];
  stale: boolean;
  is_demo: boolean;
  entity: string | null;
  check_summary: CheckSummary;
}

export interface LineageSource {
  row_id: string | null;
  raw_label: string;
  value: number | null;
  raw_value: number | null;
  scale: number;
  sign_flipped: boolean;
  source: SourceReference | null;
  mapping: Mapping | null;
}

export interface LineageNode {
  metric: string;
  name: string;
  period: string;
  kind: "derived" | "source" | "t12";
  value: number | null;
  status: CalcStatus | string;
  format: "currency" | "percent";
  formula?: {
    formula_id: string;
    name: string;
    expression: string;
    substituted?: string;
    registered_expression?: string | null;
  } | null;
  inputs?: CalcInput[];
  missing_inputs?: string[];
  month_map?: Record<string, string>;
  normalized_category?: { key: string; name: string };
  children: LineageNode[];
  sources: LineageSource[];
  confidence: number | null;
  engine?: string;
}

export interface Lineage {
  tree: LineageNode;
  leaf_sources: (LineageSource & { category: string; period: string })[];
  documents: string[];
  pages: number[];
  calculation_status: string;
}

export interface AuditEvent {
  seq: number;
  timestamp: string;
  actor: "system" | "ai" | "user" | "engine";
  agent: string | null;
  event_type: string;
  summary: string;
  details: Record<string, unknown>;
  prev_hash: string;
  hash: string;
}

export interface NumericCheck {
  checked: number;
  verified: number;
  unverified: string[];
  passed: boolean;
}

export interface Commentary {
  text: string;
  numeric_check: NumericCheck;
  note: string | null;
  provider: string;
  model: string;
  generated_at: string;
  label: string;
  disclaimer: string;
}

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  result: unknown;
}

export interface AssistantReply {
  answer: string;
  tool_calls: ToolCall[];
  numeric_check: NumericCheck;
  provider: string;
  note: string | null;
  disclaimer: string;
}

export interface Category {
  key: string;
  name: string;
  kind: "input" | "reported_subtotal" | "memo" | "excluded";
  statement: string;
  description: string;
  synonyms: string[];
}

export interface Formula {
  formula_id: string;
  metric: string;
  name: string;
  expression: string;
  inputs: string[];
  optional_inputs: string[];
  output_format: "currency" | "percent";
  description: string;
}

export interface GraphNode {
  id: string;
  label: string;
  kind: "input" | "derived";
  depth: number;
  formula_id?: string;
  expression?: string;
  format?: string;
}

export interface Meta {
  taxonomy: Category[];
  formulas: Formula[];
  graph: { nodes: GraphNode[]; edges: { from: string; to: string }[]; order: string[] };
  llm: LLMInfo;
  samples: string[];
}

// ---------------- Evaluation ----------------
export interface EvalDimension {
  key: string;
  name: string;
  description: string;
  guiding_questions: string[];
  suggested_tests: string[];
  default_weight: number;
}

export interface EvalFramework {
  dimensions: EvalDimension[];
  scale: { key: string; label: string; score: number | null }[];
  evidence_types: { key: string; label: string }[];
  disclaimer: string;
}

export interface EvalEntry {
  id: string;
  type: string;
  text: string;
  source: string;
  created_at: string;
}

export interface EvalCell {
  assessment: string;
  entries: EvalEntry[];
}

export interface EvaluationState {
  title: string;
  is_example: boolean;
  platforms: { id: string; name: string }[];
  weights: Record<string, number>;
  cells: Record<string, EvalCell>;
}

export interface EvalSummary {
  platforms: {
    platform_id: string;
    name: string;
    assessed: number;
    of: number;
    coverage: number;
    evidence_items: number;
    index: number | null;
    strengths: string[];
    limitations: string[];
    unsupported_claims: number;
  }[];
  method: string;
}
