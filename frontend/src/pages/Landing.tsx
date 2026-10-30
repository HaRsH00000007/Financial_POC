import { ArrowRight, Check, Scale, TableProperties, type LucideIcon } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/Button";
import { LayerStack, PlatformModules } from "@/features/ArchitectureDiagram";

function ModuleCard({
  icon: Icon,
  eyebrow,
  title,
  description,
  capabilities,
  cta,
  onOpen,
  footer,
}: {
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  description: string;
  capabilities: string[];
  cta: string;
  onOpen: () => void;
  footer: string;
}) {
  return (
    <div className="group flex flex-col rounded-xl border border-ink-200 bg-white shadow-card transition hover:border-ink-300 hover:shadow-pop">
      <div className="flex-1 p-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-ink-950 text-white">
            <Icon className="h-5 w-5" />
          </div>
          <span className="label-caps">{eyebrow}</span>
        </div>
        <h2 className="mt-4 text-lg font-semibold tracking-tight text-ink-950">{title}</h2>
        <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-600">{description}</p>
        <ul className="mt-5 grid gap-x-4 gap-y-2 sm:grid-cols-2">
          {capabilities.map((c) => (
            <li key={c} className="flex items-start gap-2 text-[13px] text-ink-700">
              <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ok-600" />
              {c}
            </li>
          ))}
        </ul>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink-100 px-6 py-4">
        <span className="text-xs text-ink-500">{footer}</span>
        <Button variant="primary" size="lg" onClick={onOpen} iconRight={<ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />}>
          {cta}
        </Button>
      </div>
    </div>
  );
}

export function Landing() {
  const nav = useNavigate();
  return (
    <div className="mx-auto max-w-6xl px-4 py-8 lg:px-8 lg:py-12">
      <section className="max-w-3xl">
        <div className="mb-3 inline-flex flex-wrap items-center gap-x-2 gap-y-1 whitespace-nowrap rounded-2xl border border-ink-200 bg-white px-2.5 py-1 text-[11.5px] text-ink-600">
          <span className="h-1.5 w-1.5 rounded-full bg-ai-600" /> AI reasoning
          <span className="text-ink-300">+</span>
          <span className="h-1.5 w-1.5 rounded-full bg-brand-500" /> deterministic finance
          <span className="text-ink-300">+</span>
          <span className="h-1.5 w-1.5 rounded-full bg-ok-600" /> audit-grade lineage
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-ink-950 sm:text-[34px]">Finance Intelligence Workbench</h1>
        <p className="mt-3 text-[15px] leading-relaxed text-ink-600">
          Combine generative AI with deterministic financial computation to automate finance workflows without sacrificing accuracy,
          transparency, or auditability.
        </p>
      </section>

      <section className="mt-8">
        <div className="label-caps mb-3">What do you want to explore?</div>
        <div className="grid gap-4 lg:grid-cols-2">
          <ModuleCard
            icon={TableProperties}
            eyebrow="Module 01 · Working engine"
            title="Deterministic T-12 Financial Spreading"
            description="Transform financial documents into a structured trailing-12-month financial model using AI-assisted extraction and deterministic calculations."
            capabilities={[
              "Upload financial documents",
              "Extract financial data",
              "Normalize financial categories",
              "Build T-12 financial statements",
              "Calculate financial metrics",
              "Formula-level traceability",
              "Source-level audit trail",
              "AI-generated financial commentary",
            ]}
            cta="Open T-12 Workspace"
            onOpen={() => nav("/t12")}
            footer="PDF · XLSX · CSV — or a labelled demo dataset"
          />
          <ModuleCard
            icon={Scale}
            eyebrow="Module 02 · Evaluation framework"
            title="Enterprise AI Accounting Evaluation"
            description="Evaluate enterprise AI accounting platforms using a structured framework covering accuracy, explainability, auditability, security, integration, automation, and governance."
            capabilities={[
              "Define evaluation criteria",
              "Compare platforms",
              "Score evaluation dimensions",
              "Add evidence",
              "Review strengths / limitations",
              "Generate evaluation report",
            ]}
            cta="Open Evaluation Workspace"
            onOpen={() => nav("/evaluation")}
            footer="15 dimensions · evidence-based, evaluator-assigned"
          />
        </div>
      </section>

      <section className="mt-12 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
        <div>
          <div className="label-caps">Hybrid AI Architecture</div>
          <h3 className="mt-1.5 text-lg font-semibold tracking-tight text-ink-950">AI reasons. Deterministic systems calculate. Everything is traceable.</h3>
          <p className="mt-2 text-[13.5px] leading-relaxed text-ink-600">
            Language models are excellent at reading documents and explaining results, but a statistically likely number is not an
            acceptable financial number. In this platform the LLM never produces an authoritative figure: it hands structured
            inputs to a calculation engine that evaluates explicit, versioned formulas, and every output carries its lineage back to
            the source page or cell.
          </p>
          <div className="mt-5">
            <PlatformModules />
          </div>
          <button onClick={() => nav("/architecture")} className="mt-3 inline-flex items-center gap-1 text-[13px] font-medium text-brand-600 hover:text-brand-700">
            Read the architecture notes <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
        <LayerStack />
      </section>
    </div>
  );
}
