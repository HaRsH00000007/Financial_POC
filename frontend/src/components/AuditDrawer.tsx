import clsx from "clsx";
import {
  ArrowLeft,
  Calculator,
  ChevronRight,
  Database,
  FileText,
  FunctionSquare,
  ShieldCheck,
  Tags,
  UserCheck,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/services/api";
import { fmtValue, metricName, money, periodLabel } from "@/lib/format";
import type { Lineage, LineageNode } from "@/types";
import { Drawer } from "./Overlay";
import { ErrorState, LoadingState } from "./Feedback";
import { FormulaViewer } from "./FormulaViewer";
import { StatusBadge } from "./StatusBadge";

export interface TraceTarget {
  metric: string;
  period: string;
  name?: string;
}

const METHOD_LABEL: Record<string, string> = {
  exact_synonym: "Rule: exact synonym",
  fuzzy_match: "Rule: fuzzy match",
  ai_suggested: "AI suggestion",
  user_override: "Reviewer override",
  unmapped: "Unmapped",
};

function sourceLocation(s: Lineage["leaf_sources"][number]["source"]) {
  if (!s) return "—";
  if (s.page) return `p.${s.page}`;
  if (s.sheet) return `${s.sheet}!${s.cell}`;
  return s.cell ?? s.extraction_method;
}

export function AuditDrawer({ workspaceId, target, onClose }: { workspaceId: string; target: TraceTarget | null; onClose: () => void }) {
  const [stack, setStack] = useState<TraceTarget[]>([]);
  const [data, setData] = useState<Lineage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const current = stack[stack.length - 1] ?? target;

  useEffect(() => {
    setStack(target ? [target] : []);
  }, [target]);

  useEffect(() => {
    if (!current) return;
    setData(null);
    setError(null);
    api.lineage(workspaceId, current.metric, current.period).then(setData, (e) => setError(e.message));
  }, [workspaceId, current?.metric, current?.period]);

  const drill = (n: LineageNode) => setStack((s) => [...s, { metric: n.metric, period: n.period, name: n.name }]);
  const t = data?.tree;

  return (
    <Drawer
      open={!!target}
      onClose={onClose}
      width="max-w-3xl"
      title={
        <span className="flex items-center gap-2">
          {stack.length > 1 && (
            <button onClick={() => setStack((s) => s.slice(0, -1))} className="rounded p-0.5 text-ink-500 hover:bg-ink-100" aria-label="Back">
              <ArrowLeft className="h-4 w-4" />
            </button>
          )}
          Audit Trail
        </span>
      }
      subtitle={
        <span className="flex flex-wrap items-center gap-1">
          {stack.map((s, i) => (
            <span key={i} className="inline-flex items-center gap-1">
              {i > 0 && <ChevronRight className="h-3 w-3" />}
              <button className="hover:text-ink-900" onClick={() => setStack((st) => st.slice(0, i + 1))}>
                {(t && i === stack.length - 1 ? t.name : s.name) ?? metricName(s.metric)} · {periodLabel(s.period)}
              </button>
            </span>
          ))}
        </span>
      }
    >
      {error && <div className="p-5"><ErrorState message={error} /></div>}
      {!data && !error && <LoadingState lines={8} className="p-5" />}
      {t && data && (
        <div className="space-y-5 p-5">
          {/* Headline */}
          <div className="rounded-lg border border-ink-200 bg-ink-50/60 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="label-caps">Metric</div>
                <div className="text-lg font-semibold text-ink-950">{t.name}</div>
                <div className="text-xs text-ink-500">{periodLabel(t.period)}</div>
              </div>
              <div className="text-right">
                <div className="label-caps">Value</div>
                <div className="num text-2xl font-semibold text-ink-950">{fmtValue(t.value, t.format)}</div>
              </div>
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2.5 border-t border-ink-200 pt-3 text-xs sm:grid-cols-4">
              <Field label="Calculation status">
                <StatusBadge kind={t.status as any} size="xs" />
              </Field>
              <Field label="Engine">
                <span className="font-mono text-[11px]">{t.engine ?? (t.kind === "source" ? "source value" : "—")}</span>
              </Field>
              <Field label="Source">
                <span className="break-all">{data.documents.join(", ") || "Reviewer entry"}</span>
              </Field>
              <Field label={data.pages.length ? "Page(s)" : "Location"}>
                {data.pages.length ? data.pages.join(", ") : sourceLocation(data.leaf_sources[0]?.source ?? null)}
              </Field>
              <Field label="Extraction confidence">
                <span className="num">{t.confidence == null ? "—" : `${Math.round(t.confidence * 100)}% (lowest input)`}</span>
              </Field>
              <Field label="Source values">
                <span className="num">{data.leaf_sources.length}</span>
              </Field>
              <Field label="AI involvement">None in arithmetic</Field>
              <Field label="Formula">
                <span className="font-mono text-[11px]">{t.formula?.formula_id ?? "—"}</span>
              </Field>
            </dl>
          </div>

          {/* Chain */}
          <section>
            <h4 className="label-caps mb-2">Lineage chain</h4>
            <ol className="relative space-y-2 border-l border-ink-200 pl-5">
              <ChainStep icon={FileText} title="Source document" tone="trust">
                {data.documents.length ? (
                  data.documents.map((d) => (
                    <div key={d} className="text-[13px] text-ink-800">
                      {d}{" "}
                      {d.startsWith("Reviewer") ? (
                        <span className="text-warn-700">· manual entries (audited, with justification)</span>
                      ) : (
                        data.pages.length > 0 && <span className="text-ink-500">· pages {data.pages.join(", ")}</span>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-[13px] text-ink-600">Reviewer-provided values (audited)</div>
                )}
              </ChainStep>
              <ChainStep icon={Database} title={`Extracted values (${data.leaf_sources.length})`} tone="ai">
                <LeafTable leaves={data.leaf_sources} />
              </ChainStep>
              <ChainStep icon={Tags} title="Normalized categories" tone="ai">
                <NormalizedList leaves={data.leaf_sources} />
              </ChainStep>
              {t.formula && (
                <ChainStep icon={FunctionSquare} title="Formula (deterministic)" tone="det">
                  <FormulaViewer formulaId={t.formula.formula_id} name={t.formula.name} expression={t.formula.expression} substituted={t.formula.substituted} />
                </ChainStep>
              )}
              <ChainStep icon={Calculator} title="Calculated result" tone="det" last>
                <div className="flex items-center gap-2">
                  <span className="num text-[15px] font-semibold text-ink-950">{fmtValue(t.value, t.format)}</span>
                  <StatusBadge kind={t.status as any} size="xs" />
                </div>
                {t.missing_inputs && t.missing_inputs.length > 0 && (
                  <p className="mt-1 text-xs text-risk-700">
                    Not computed - missing input(s): {t.missing_inputs.map((m) => t.month_map?.[m] ? periodLabel(t.month_map[m]) : m).join(", ")}. Values are never estimated.
                  </p>
                )}
              </ChainStep>
            </ol>
          </section>

          {/* Tree */}
          {t.children.length > 0 && (
            <section>
              <h4 className="label-caps mb-2">Calculation inputs · click to drill down</h4>
              <div className="overflow-hidden rounded-lg border border-ink-200">
                {t.children.map((c, i) => (
                  <TreeRow key={i} node={c} depth={0} onDrill={drill} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </Drawer>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[10.5px] font-medium uppercase tracking-wide text-ink-400">{label}</dt>
      <dd className="mt-0.5 text-ink-800">{children}</dd>
    </div>
  );
}

function ChainStep({ icon: Icon, title, children, tone, last }: { icon: any; title: string; children: ReactNode; tone: "ai" | "det" | "trust"; last?: boolean }) {
  const ring = { ai: "bg-ai-50 text-ai-700 ring-ai-100", det: "bg-brand-50 text-brand-700 ring-brand-100", trust: "bg-ok-50 text-ok-700 ring-ok-100" }[tone];
  return (
    <li className={clsx("relative", !last && "pb-1")}>
      <span className={clsx("absolute -left-[31px] top-0.5 flex h-5 w-5 items-center justify-center rounded-full ring-1", ring)}>
        <Icon className="h-3 w-3" />
      </span>
      <div className="text-xs font-semibold text-ink-700">{title}</div>
      <div className="mt-1.5">{children}</div>
    </li>
  );
}

function LeafTable({ leaves }: { leaves: Lineage["leaf_sources"] }) {
  const [all, setAll] = useState(false);
  const shown = all ? leaves : leaves.slice(0, 8);
  if (!leaves.length) return <p className="text-xs text-ink-500">No source values (all inputs derived or missing).</p>;
  return (
    <div className="overflow-x-auto rounded-md border border-ink-200">
      <table className="w-full text-xs">
        <thead className="bg-ink-50 text-left text-[10.5px] uppercase tracking-wide text-ink-500">
          <tr>
            <th className="px-2 py-1.5 font-medium">Source label</th>
            <th className="px-2 py-1.5 font-medium">Period</th>
            <th className="px-2 py-1.5 font-medium">Location</th>
            <th className="px-2 py-1.5 font-medium">Raw</th>
            <th className="px-2 py-1.5 text-right font-medium">Value</th>
            <th className="px-2 py-1.5 text-right font-medium">Conf.</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-100">
          {shown.map((l, i) => {
            const manual = l.source?.extraction_method.includes("manual") || l.source?.extraction_method.includes("attested");
            return (
              <tr key={i} className={clsx(manual && "bg-warn-50/60")}>
                <td className="px-2 py-1.5 text-ink-800">
                  {manual && <UserCheck className="mr-1 inline h-3 w-3 text-warn-700" />}
                  {l.raw_label}
                </td>
                <td className="px-2 py-1.5 text-ink-600">{periodLabel(l.period, true)}</td>
                <td className="px-2 py-1.5 font-mono text-[11px] text-ink-600">{sourceLocation(l.source)}</td>
                <td className="max-w-[140px] truncate px-2 py-1.5 font-mono text-[11px] text-ink-500" title={l.source?.raw_text ?? ""}>
                  {l.source?.raw_text ?? "—"}
                </td>
                <td className="num px-2 py-1.5 text-right text-ink-900">
                  {money(l.value)}
                  {l.sign_flipped && <span className="ml-1 text-[10px] text-warn-700">±</span>}
                </td>
                <td className="num px-2 py-1.5 text-right text-ink-600">{l.source ? `${Math.round(l.source.confidence * 100)}%` : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {leaves.length > 8 && (
        <button className="w-full border-t border-ink-100 py-1.5 text-[11px] font-medium text-brand-600 hover:bg-ink-50" onClick={() => setAll(!all)}>
          {all ? "Show fewer" : `Show all ${leaves.length} source values`}
        </button>
      )}
    </div>
  );
}

function NormalizedList({ leaves }: { leaves: Lineage["leaf_sources"] }) {
  const groups = new Map<string, { labels: Set<string>; methods: Set<string> }>();
  leaves.forEach((l) => {
    const g = groups.get(l.category) ?? { labels: new Set(), methods: new Set() };
    g.labels.add(l.raw_label);
    if (l.mapping) g.methods.add(METHOD_LABEL[l.mapping.method] ?? l.mapping.method);
    else g.methods.add("Reviewer attestation");
    groups.set(l.category, g);
  });
  return (
    <div className="flex flex-wrap gap-1.5">
      {[...groups.entries()].map(([cat, g]) => (
        <div key={cat} className="rounded-md border border-ink-200 bg-white px-2 py-1 text-[11.5px]">
          <span className="text-ink-500">{[...g.labels].map((l) => `"${l}"`).join(", ")}</span>
          <span className="mx-1 text-ink-400">→</span>
          <span className="font-semibold text-ink-900">{cat}</span>
          <span className="ml-1.5 text-[10.5px] text-ink-400">{[...g.methods].join(", ")}</span>
        </div>
      ))}
    </div>
  );
}

function TreeRow({ node, depth, onDrill }: { node: LineageNode; depth: number; onDrill: (n: LineageNode) => void }) {
  const [open, setOpen] = useState(depth < 1 && node.children.length > 0 && node.children.length <= 4);
  const hasKids = node.children.length > 0;
  return (
    <div className="border-b border-ink-100 last:border-b-0">
      <div className="flex items-center gap-2 px-3 py-2 hover:bg-ink-50" style={{ paddingLeft: 12 + depth * 18 }}>
        <button
          onClick={() => setOpen(!open)}
          className={clsx("flex h-4 w-4 items-center justify-center rounded text-ink-400", hasKids ? "hover:bg-ink-200" : "invisible")}
          aria-label="Expand"
        >
          <ChevronRight className={clsx("h-3.5 w-3.5 transition-transform", open && "rotate-90")} />
        </button>
        <button onClick={() => onDrill(node)} className="flex min-w-0 flex-1 items-center gap-2 text-left">
          <span className="truncate text-[13px] text-ink-900 hover:text-brand-600">{node.name}</span>
          <span className="text-[11px] text-ink-400">{periodLabel(node.period, true)}</span>
          {node.formula && <span className="hidden font-mono text-[10.5px] text-ink-400 sm:inline">{node.formula.formula_id}</span>}
          {node.kind === "source" && <span className="text-[10.5px] text-ai-700">source</span>}
        </button>
        {node.status !== "DETERMINISTIC" && <StatusBadge kind={node.status as any} size="xs" />}
        {node.status === "DETERMINISTIC" && <ShieldCheck className="h-3.5 w-3.5 text-ok-600" aria-label="deterministic" />}
        <span className="num w-28 text-right text-[13px] font-medium text-ink-900">{fmtValue(node.value, node.format)}</span>
      </div>
      {open && node.children.map((c, i) => <TreeRow key={i} node={c} depth={depth + 1} onDrill={onDrill} />)}
    </div>
  );
}
