// Presentation-only formatting. No financial arithmetic happens in the browser:
// every value shown is produced by the backend deterministic engine.

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function periodLabel(p: string, short = false): string {
  if (p === "T12") return "T-12";
  if (p === "T12_PRIOR") return "Prior T-12";
  if (p === "YOY") return "T-12 vs prior T-12";
  const [y, m] = p.split("-");
  if (!m) return p;
  return short ? `${MONTHS[+m - 1]} '${y.slice(2)}` : `${MONTHS[+m - 1]} ${y}`;
}

export function money(v: number | null | undefined, opts: { compact?: boolean; cents?: boolean } = {}): string {
  if (v === null || v === undefined) return "—";
  const neg = v < 0;
  const a = Math.abs(v);
  let s: string;
  if (opts.compact && a >= 1_000_000) s = `$${(a / 1_000_000).toFixed(2)}M`;
  else if (opts.compact && a >= 10_000) s = `$${(a / 1_000).toFixed(1)}K`;
  else s = `$${a.toLocaleString("en-US", { minimumFractionDigits: opts.cents ? 2 : 0, maximumFractionDigits: opts.cents ? 2 : 0 })}`;
  return neg ? `(${s})` : s;
}

export function plain(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const s = Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 2 });
  return v < 0 ? `(${s})` : s;
}

export function pct(v: number | null | undefined, signed = false, digits = 1): string {
  if (v === null || v === undefined) return "—";
  const s = (v * 100).toFixed(digits);
  return signed && v > 0 ? `+${s}%` : `${s}%`;
}

export function fmtValue(v: number | null | undefined, format: "currency" | "percent" = "currency", compact = false) {
  return format === "percent" ? pct(v) : money(v, { compact });
}

export function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

export function time(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export const METRIC_NAMES: Record<string, string> = {
  revenue: "Revenue",
  cogs: "COGS",
  gross_profit: "Gross Profit",
  operating_expenses: "Operating Expenses",
  payroll: "Payroll",
  rent: "Rent & Occupancy",
  sales_marketing: "Sales & Marketing",
  technology: "Technology & Software",
  general_admin: "General & Administrative",
  other_opex: "Other Operating Expense",
  ebitda: "EBITDA",
  depreciation: "Depreciation & Amortization",
  interest: "Interest Expense",
  taxes: "Income Taxes",
  net_income: "Net Income",
  gross_margin: "Gross Margin %",
  ebitda_margin: "EBITDA Margin %",
  net_margin: "Net Margin %",
};

export const metricName = (k: string) => METRIC_NAMES[k] ?? k.replace(/_/g, " ");

export const PERCENT_METRICS = new Set(["gross_margin", "ebitda_margin", "net_margin"]);
export const formatOf = (k: string): "currency" | "percent" => (PERCENT_METRICS.has(k) ? "percent" : "currency");
