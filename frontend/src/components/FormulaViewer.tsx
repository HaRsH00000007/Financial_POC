import clsx from "clsx";
import { useMemo, useState } from "react";
import { fmtValue, metricName } from "@/lib/format";
import type { GraphNode } from "@/types";

/** Renders a formula expression with named inputs highlighted, plus its substituted form. */
export function FormulaViewer({
  formulaId,
  expression,
  substituted,
  name,
  compact,
}: {
  formulaId: string;
  expression: string;
  substituted?: string;
  name?: string;
  compact?: boolean;
}) {
  const tokens = expression.split(/(\s+|[()+\-*/])/).filter((t) => t !== "");
  return (
    <div className={clsx("rounded-md border border-brand-100 bg-brand-50/50", compact ? "px-2.5 py-2" : "px-3 py-2.5")}>
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-[10.5px] font-semibold uppercase tracking-wide text-brand-700">{name ?? "Formula"}</span>
        <span className="rounded bg-white px-1.5 py-0.5 font-mono text-[10.5px] text-brand-700 ring-1 ring-brand-100">{formulaId}</span>
      </div>
      <div className="font-mono text-[12.5px] leading-relaxed text-ink-900">
        {tokens.map((t, i) =>
          /^[a-z_][a-z0-9_]*$/i.test(t) ? (
            <span key={i} className="rounded bg-white px-1 text-brand-700 ring-1 ring-brand-100" title={metricName(t)}>
              {t}
            </span>
          ) : (
            <span key={i} className="text-ink-500">{t}</span>
          ),
        )}
      </div>
      {substituted && (
        <div className="num mt-1.5 border-t border-brand-100 pt-1.5 font-mono text-[12px] text-ink-600">= {substituted}</div>
      )}
    </div>
  );
}

/** Layered DAG of the formula registry. Columns = dependency depth. */
export function DependencyGraph({
  nodes,
  edges,
  values,
  notReported = [],
  onSelect,
}: {
  nodes: GraphNode[];
  edges: { from: string; to: string }[];
  values?: Record<string, { value: number | null; status: string }>;
  notReported?: string[];
  onSelect?: (id: string) => void;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const layout = useMemo(() => {
    const cols: Record<number, GraphNode[]> = {};
    nodes.forEach((n) => (cols[n.depth] ??= []).push(n));
    const maxDepth = Math.max(...Object.keys(cols).map(Number));
    const colW = 190;
    const nodeW = 150;
    const nodeH = 42;
    const gap = 12;
    const tallest = Math.max(...Object.values(cols).map((c) => c.length));
    const height = tallest * (nodeH + gap) + 20;
    const pos: Record<string, { x: number; y: number }> = {};
    Object.entries(cols).forEach(([d, list]) => {
      const colH = list.length * (nodeH + gap) - gap;
      const y0 = (height - colH) / 2;
      list.forEach((n, i) => (pos[n.id] = { x: 10 + Number(d) * colW, y: y0 + i * (nodeH + gap) }));
    });
    return { pos, width: 10 + maxDepth * colW + nodeW + 10, height, nodeW, nodeH };
  }, [nodes]);

  const related = useMemo(() => {
    if (!hover) return null;
    const set = new Set([hover]);
    const walk = (id: string, dir: "up" | "down") =>
      edges.forEach((e) => {
        const [a, b] = dir === "up" ? [e.to, e.from] : [e.from, e.to];
        if (a === id && !set.has(b)) {
          set.add(b);
          walk(b, dir);
        }
      });
    walk(hover, "up");
    walk(hover, "down");
    return set;
  }, [hover, edges]);

  const { pos, width, height, nodeW, nodeH } = layout;
  return (
    <div className="scroll-thin overflow-x-auto">
      <svg width={width} height={height} className="block" role="img" aria-label="Formula dependency graph">
        {edges.map((e, i) => {
          const a = pos[e.from];
          const b = pos[e.to];
          if (!a || !b) return null;
          const x1 = a.x + nodeW;
          const y1 = a.y + nodeH / 2;
          const x2 = b.x;
          const y2 = b.y + nodeH / 2;
          const mx = (x1 + x2) / 2;
          const on = related ? related.has(e.from) && related.has(e.to) : false;
          return (
            <path
              key={i}
              d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`}
              fill="none"
              stroke={on ? "#2a78d6" : "#cfd5e1"}
              strokeWidth={on ? 2 : 1.25}
              opacity={related && !on ? 0.35 : 1}
            />
          );
        })}
        {nodes.map((n) => {
          const p = pos[n.id];
          const v = values?.[n.id];
          const missing = notReported.includes(n.id);
          const dim = related && !related.has(n.id);
          const derived = n.kind === "derived";
          const incomplete = v && v.status !== "DETERMINISTIC";
          return (
            <g
              key={n.id}
              transform={`translate(${p.x},${p.y})`}
              onMouseEnter={() => setHover(n.id)}
              onMouseLeave={() => setHover(null)}
              onClick={() => !missing && onSelect?.(n.id)}
              className={clsx(!missing && onSelect && "cursor-pointer")}
              opacity={dim ? 0.35 : 1}
            >
              <rect
                width={nodeW}
                height={nodeH}
                rx={6}
                fill={missing ? "#f6f7fa" : derived ? "#f1f6fd" : "#ffffff"}
                stroke={incomplete ? "#c2383c" : hover === n.id ? "#2a78d6" : derived ? "#b9d0f3" : "#d9dde6"}
                strokeDasharray={missing ? "4 3" : undefined}
              />
              <text x={10} y={17} fontSize={11.5} fontWeight={600} fill={missing ? "#8b94ad" : "#111a2e"}>
                {derived ? n.label : metricName(n.id)}
              </text>
              <text x={10} y={32} fontSize={10.5} fill={incomplete ? "#a3262a" : "#667090"} className="num" fontFamily="JetBrains Mono, monospace">
                {missing ? "not reported" : v ? (v.value === null ? v.status.toLowerCase() : fmtValue(v.value, (n.format as any) ?? (n.id.endsWith("margin") ? "percent" : "currency"), true)) : n.formula_id ?? "source input"}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
