import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { money, pct, periodLabel } from "@/lib/format";

// Validated categorical slots (reference palette, light mode): blue, orange, aqua.
export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a"];
const AXIS = { fontSize: 11, fill: "#667090" };
const GRID = "#eceff4";

export interface SeriesPoint {
  period: string;
  [k: string]: number | null | string;
}

function ChartTooltip({ active, payload, label, format }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-ink-200 bg-white px-3 py-2 text-xs shadow-pop">
      <div className="mb-1 font-semibold text-ink-900">{periodLabel(label)}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-ink-600">
            <span className="h-2 w-2 rounded-sm" style={{ background: p.color ?? p.payload?.fill }} />
            {p.name}
          </span>
          <span className="num font-medium text-ink-900">
            {p.value === null || p.value === undefined ? "incomplete" : format === "percent" ? pct(p.value) : money(p.value)}
          </span>
        </div>
      ))}
      <div className="mt-1.5 border-t border-ink-100 pt-1 text-[10.5px] text-ink-400">Engine value · click to trace</div>
    </div>
  );
}

const tickMoney = (v: number) => (Math.abs(v) >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : `$${Math.round(v / 1e3)}K`);

/** Single-series monthly bars. Missing (INCOMPLETE) months render as a dashed placeholder. */
export function MonthlyBarChart({
  data,
  dataKey,
  name,
  color = SERIES[0],
  onSelect,
  height = 220,
}: {
  data: SeriesPoint[];
  dataKey: string;
  name: string;
  color?: string;
  onSelect?: (period: string) => void;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }} barCategoryGap="22%">
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="period" tickFormatter={(p) => periodLabel(p, true).split(" ")[0]} tick={AXIS} axisLine={{ stroke: "#d9dde6" }} tickLine={false} interval={0} />
        <YAxis tickFormatter={tickMoney} tick={AXIS} axisLine={false} tickLine={false} width={52} />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(42,120,214,0.06)" }} />
        <Bar dataKey={dataKey} name={name} fill={color} radius={[4, 4, 0, 0]} maxBarSize={34} isAnimationActive={false} onClick={(d: any) => onSelect?.(d.period)} className="cursor-pointer">
          {data.map((d, i) => (
            <Cell key={i} fill={(d[dataKey] as number) < 0 ? "#e34948" : color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function MultiLineChart({
  data,
  series,
  format = "percent",
  onSelect,
  height = 220,
}: {
  data: SeriesPoint[];
  series: { key: string; name: string }[];
  format?: "percent" | "currency";
  onSelect?: (period: string, key: string) => void;
  height?: number;
}) {
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-3 text-[11.5px] text-ink-600" aria-label="Legend">
        {series.map((s, i) => (
          <span key={s.key} className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded" style={{ background: SERIES[i] }} />
            {s.name}
          </span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={data}
          margin={{ top: 8, right: 16, left: 0, bottom: 0 }}
          onClick={(e: any) => e?.activeLabel && onSelect?.(e.activeLabel, series[0].key)}
        >
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="period" tickFormatter={(p) => periodLabel(p, true).split(" ")[0]} tick={AXIS} axisLine={{ stroke: "#d9dde6" }} tickLine={false} interval={0} />
          <YAxis tickFormatter={(v) => (format === "percent" ? `${Math.round(v * 100)}%` : tickMoney(v))} tick={AXIS} axisLine={false} tickLine={false} width={44} />
          <Tooltip content={<ChartTooltip format={format} />} cursor={{ stroke: "#b6bccb", strokeDasharray: "3 3" }} />
          {series.map((s, i) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stroke={SERIES[i]}
              strokeWidth={2}
              dot={{ r: 3, strokeWidth: 2, fill: "#fff" }}
              activeDot={{ r: 5, strokeWidth: 2, stroke: "#fff" }}
              connectNulls={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function HorizontalBars({
  data,
  onSelect,
}: {
  data: { key: string; name: string; value: number | null }[];
  onSelect?: (key: string) => void;
}) {
  const max = Math.max(...data.map((d) => d.value ?? 0), 1);
  return (
    <div className="space-y-2">
      {data.map((d) => (
        <button key={d.key} onClick={() => onSelect?.(d.key)} className="group block w-full text-left" title="Trace calculation">
          <div className="mb-1 flex items-baseline justify-between gap-2 text-xs">
            <span className="truncate text-ink-700 group-hover:text-brand-600">{d.name}</span>
            <span className="num shrink-0 text-ink-900">
              {money(d.value, { compact: true })}
            </span>
          </div>
          <div className="h-2 rounded-full bg-ink-100">
            <div className="h-2 rounded-full transition-all group-hover:opacity-80" style={{ width: `${((d.value ?? 0) / max) * 100}%`, background: SERIES[0] }} />
          </div>
        </button>
      ))}
    </div>
  );
}
