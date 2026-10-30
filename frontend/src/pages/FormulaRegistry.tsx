import { Card, CardHeader } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/Feedback";
import { DependencyGraph, FormulaViewer } from "@/components/FormulaViewer";
import { LayerTag } from "@/components/StatusBadge";
import { useMeta } from "@/hooks/useMeta";

export function FormulaRegistry() {
  const { meta, error, reload } = useMeta();
  if (error) return <div className="p-6"><ErrorState message={error} onRetry={reload} /></div>;
  if (!meta) return <div className="p-6"><Card><LoadingState lines={8} /></Card></div>;
  return (
    <div className="mx-auto max-w-[1440px] space-y-4 px-4 py-5 lg:px-6">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-ink-950">Formula Registry</h1>
        <p className="text-[13px] text-ink-500">
          Every calculation is declared here as data and evaluated by the deterministic engine. Formulas are versioned by ID and referenced in every result and audit event.
        </p>
      </div>
      <Card>
        <CardHeader title="Dependency graph" subtitle="Topological evaluation order · hover a node to highlight its upstream and downstream lineage" actions={<LayerTag layer="deterministic" />} />
        <div className="p-4">
          <DependencyGraph nodes={meta.graph.nodes} edges={meta.graph.edges} />
        </div>
      </Card>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {meta.formulas.map((f) => (
          <Card key={f.formula_id} className="p-4">
            <div className="mb-2 text-[13px] font-semibold text-ink-950">{f.name}</div>
            <FormulaViewer formulaId={f.formula_id} expression={f.expression} name={f.output_format === "percent" ? "Ratio" : "Currency"} compact />
            {f.description && <p className="mt-2 text-xs leading-relaxed text-ink-500">{f.description}</p>}
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader title="Normalization taxonomy" subtitle="Canonical categories and the synonyms rules match exactly" />
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full min-w-[640px] text-[13px]">
            <thead className="bg-ink-50 text-left text-[10.5px] uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2 font-medium">Category</th>
                <th className="px-2 py-2 font-medium">Role</th>
                <th className="px-4 py-2 font-medium">Synonyms</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {meta.taxonomy.map((c) => (
                <tr key={c.key}>
                  <td className="px-4 py-2">
                    <div className="font-medium text-ink-900">{c.name}</div>
                    <div className="font-mono text-[11px] text-ink-400">{c.key}</div>
                  </td>
                  <td className="px-2 py-2 text-xs text-ink-600">{c.kind.replace("_", " ")}</td>
                  <td className="px-4 py-2 text-xs text-ink-500">{c.synonyms.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
