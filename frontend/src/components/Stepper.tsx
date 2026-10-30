import clsx from "clsx";
import { Check } from "lucide-react";

export interface Step {
  key: string;
  label: string;
  hint?: string;
  layer?: "probabilistic" | "deterministic" | "human" | "trust";
}

const LAYER_DOT = {
  probabilistic: "bg-ai-600",
  deterministic: "bg-brand-500",
  human: "bg-warn-600",
  trust: "bg-ok-600",
};

export function Stepper({
  steps,
  current,
  maxReached,
  onSelect,
}: {
  steps: Step[];
  current: number;
  maxReached: number;
  onSelect: (i: number) => void;
}) {
  return (
    <nav aria-label="Workflow progress" className="scroll-thin overflow-x-auto">
      <ol className="flex min-w-max items-center gap-1">
        {steps.map((s, i) => {
          const done = i < current || (i <= maxReached && i !== current);
          const active = i === current;
          const reachable = i <= maxReached;
          return (
            <li key={s.key} className="flex items-center">
              <button
                disabled={!reachable}
                onClick={() => onSelect(i)}
                className={clsx(
                  "group flex items-center gap-2 rounded-md px-2.5 py-1.5 text-left transition-colors",
                  active ? "bg-ink-950 text-white" : reachable ? "text-ink-700 hover:bg-ink-100" : "cursor-not-allowed text-ink-400",
                )}
              >
                <span
                  className={clsx(
                    "flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-semibold",
                    active ? "bg-white text-ink-950" : done ? "bg-ok-600 text-white" : "bg-ink-100 text-ink-500",
                  )}
                >
                  {done && !active ? <Check className="h-3 w-3" /> : i + 1}
                </span>
                <span className="text-[12.5px] font-medium">{s.label}</span>
                {s.layer && <span className={clsx("h-1.5 w-1.5 rounded-full", LAYER_DOT[s.layer])} title={s.layer} />}
              </button>
              {i < steps.length - 1 && <span className="mx-0.5 h-px w-4 bg-ink-200" />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
