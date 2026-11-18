// Presentation-only formatting. No financial arithmetic happens in the browser:
// every value shown is produced by the backend deterministic engine.
import type { ValueFormat } from "@/types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Display currency for the active workspace. T-12 = USD; annual reports = INR crore (as printed). */
type CurrencyMode = { code: "USD" } | { code: "INR"; unit: string };
let CURRENCY: CurrencyMode = { code: "USD" };
export function setCurrency(mode: CurrencyMode) {
  CURRENCY = mode;
}
export const currencyLabel = () => (CURRENCY.code === "INR" ? `₹ ${CURRENCY.unit}` : "USD");

export function periodLabel(p: string, short = false): string {
  if (p === "T12") return "T-12";
  if (p === "T12_PRIOR") return "Prior T-12";
  if (p === "YOY") return "T-12 vs prior T-12";
  const fy = /^FY(\d{4})$/.exec(p);
  if (fy) {
    const end = +fy[1];
    return short ? `FY${String(end).slice(2)}` : `FY ${end - 1}-${String(end).slice(2)}`;
  }
  const [y, m] = p.split("-");
  if (!m) return p;
  return short ? `${MONTHS[+m - 1]} '${y.slice(2)}` : `${MONTHS[+m - 1]} ${y}`;
}

function inr(v: number, compact?: boolean): string {
  const unit = CURRENCY.code === "INR" ? CURRENCY.unit : "crore";
  const short = unit === "crore" ? "Cr" : unit;
  if (compact && unit === "crore" && v >= 1_00_000) return `₹${(v / 1_00_000).toFixed(2)} L Cr`;
  return `₹${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}${compact ? ` ${short}` : ""}`;
}

export function money(v: number | null | undefined, opts: { compact?: boolean; cents?: boolean } = {}): string {
  if (v === null || v === undefined) return "—";
  const neg = v < 0;
  const a = Math.abs(v);
  let s: string;
  if (CURRENCY.code === "INR") s = inr(a, opts.compact);
  else if (opts.compact && a >= 1_000_000) s = `$${(a / 1_000_000).toFixed(2)}M`;
  else if (opts.compact && a >= 10_000) s = `$${(a / 1_000).toFixed(1)}K`;
  else s = `$${a.toLocaleString("en-US", { minimumFractionDigits: opts.cents ? 2 : 0, maximumFractionDigits: opts.cents ? 2 : 0 })}`;
  return neg ? `(${s})` : s;
}

export function plain(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const s = Math.abs(v).toLocaleString(CURRENCY.code === "INR" ? "en-IN" : "en-US", { maximumFractionDigits: 2 });
  return v < 0 ? `(${s})` : s;
}

export function multiple(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : `${v.toFixed(2)}x`;
}

export function pct(v: number | null | undefined, signed = false, digits = 1): string {
  if (v === null || v === undefined) return "—";
  const s = (v * 100).toFixed(digits);
  return signed && v > 0 ? `+${s}%` : `${s}%`;
}

export function fmtValue(v: number | null | undefined, format: ValueFormat = "currency", compact = false) {
  if (format === "percent") return pct(v);
  if (format === "multiple") return multiple(v);
  if (format === "number") return v === null || v === undefined ? "—" : v.toFixed(2);
  return money(v, { compact });
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

// Annual-report metrics (names come from the backend registry; this map covers display only).
const ANNUAL_NAMES: Record<string, string> = {
  profit: "Profit for the Year",
  pbt: "Profit Before Associates & Tax",
  total_income: "Total Income",
  total_expenses: "Total Expenses",
  total_tax: "Total Tax",
  ebitda_ex_oi: "EBITDA excl. Other Income",
  effective_tax_rate: "Effective Tax Rate",
  interest_cover: "Interest Cover",
  total_assets: "Total Assets",
  total_equity: "Total Equity",
  total_liabilities: "Total Liabilities",
  total_debt: "Total Borrowings",
  net_debt: "Net Debt",
  debt_to_equity: "Debt / Equity",
  net_debt_to_ebitda: "Net Debt / EBITDA",
  current_ratio: "Current Ratio",
  roe: "Return on Equity",
  cfo: "Operating Cash Flow",
  cfi: "Investing Cash Flow",
  cff: "Financing Cash Flow",
  capex: "Capital Expenditure",
  fcf: "Free Cash Flow",
  cash_conversion: "Cash Conversion",
  net_cash_change: "Net Change in Cash",
  closing_cash: "Closing Cash",
  revenue_growth: "Revenue Growth",
  ebitda_growth: "EBITDA Growth",
  profit_growth: "Profit Growth",
  cfo_growth: "CFO Growth",
  other_income: "Other Income",
  finance_costs: "Finance Costs",
  materials_cost: "Cost of Materials Consumed",
  purchases_traded: "Purchase of Stock-in-Trade",
  inventory_change: "Changes in Inventories",
  excise_duty: "Excise Duty",
  employee_costs: "Employee Benefits Expense",
  other_expenses: "Other Expenses",
  current_tax: "Current Tax",
  deferred_tax: "Deferred Tax",
  cash_equivalents: "Cash and Cash Equivalents",
  current_investments: "Current Investments",
  borrowings_nc: "Borrowings - Non-Current",
  borrowings_c: "Borrowings - Current",
};
Object.entries(ANNUAL_NAMES).forEach(([k, v]) => (METRIC_NAMES[k] ??= v));

const ANNUAL_PERCENT = ["effective_tax_rate", "roe", "cash_conversion", "revenue_growth", "ebitda_growth", "profit_growth", "cfo_growth", "total_assets_growth", "net_debt_growth"];
ANNUAL_PERCENT.forEach((k) => PERCENT_METRICS.add(k));
export const MULTIPLE_METRICS = new Set(["interest_cover", "debt_to_equity", "net_debt_to_ebitda", "current_ratio"]);
export const valueFormat = (k: string): ValueFormat => (PERCENT_METRICS.has(k) ? "percent" : MULTIPLE_METRICS.has(k) ? "multiple" : "currency");
