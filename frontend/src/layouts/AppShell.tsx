import clsx from "clsx";
import {
  BookOpenCheck,
  ChevronRight,
  Cpu,
  FunctionSquare,
  LayoutGrid,
  Menu,
  Scale,
  Sparkles,
  TableProperties,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useMeta } from "@/hooks/useMeta";
import { Tooltip } from "@/components/Overlay";
import { ErrorBoundary } from "@/components/ErrorBoundary";

const NAV = [
  { to: "/", label: "Workbench", icon: LayoutGrid, end: true },
  { to: "/t12", label: "T-12 Spreading", icon: TableProperties },
  { to: "/evaluation", label: "AI Accounting Evaluation", icon: Scale },
  { section: "Platform" },
  { to: "/formulas", label: "Formula Registry", icon: FunctionSquare },
  { to: "/architecture", label: "Architecture", icon: BookOpenCheck },
] as const;

const CRUMBS: Record<string, string> = {
  t12: "Deterministic T-12 Financial Spreading",
  evaluation: "Enterprise AI Accounting Evaluation",
  formulas: "Formula Registry",
  architecture: "Hybrid AI Architecture",
};

function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2.5 px-1">
      <div className="flex h-7 w-7 items-center justify-center rounded-md bg-white text-ink-950">
        <svg viewBox="0 0 32 32" className="h-5 w-5">
          <path d="M8 23V9h11M8 16h8" stroke="currentColor" strokeWidth="3.2" fill="none" strokeLinecap="round" />
          <circle cx="23.5" cy="21.5" r="3.2" fill="#2a78d6" />
        </svg>
      </div>
      <div className="leading-tight">
        <div className="text-[13px] font-semibold text-white">Finance Intelligence</div>
        <div className="text-[11px] text-ink-400">Workbench · POC</div>
      </div>
    </Link>
  );
}

function SideNav({ onNavigate }: { onNavigate?: () => void }) {
  const { meta } = useMeta();
  return (
    <div className="flex h-full flex-col bg-ink-950 px-3 py-4">
      <Brand />
      <nav className="mt-6 flex-1 space-y-0.5">
        {NAV.map((n, i) =>
          "section" in n ? (
            <div key={i} className="px-2 pb-1 pt-5 text-[10.5px] font-semibold uppercase tracking-wider text-ink-500">
              {n.section}
            </div>
          ) : (
            <NavLink
              key={n.to}
              to={n.to}
              end={"end" in n ? n.end : false}
              onClick={onNavigate}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-[13px] transition-colors",
                  isActive ? "bg-white/10 font-medium text-white" : "text-ink-300 hover:bg-white/5 hover:text-white",
                )
              }
            >
              <n.icon className="h-4 w-4 shrink-0" />
              {n.label}
            </NavLink>
          ),
        )}
      </nav>
      <div className="space-y-2 rounded-lg border border-white/10 bg-white/[0.03] p-3 text-[11.5px]">
        <div className="flex items-center gap-1.5 text-ink-300">
          <Sparkles className="h-3.5 w-3.5 text-ai-100" /> AI layer
        </div>
        <div className="font-medium text-white">{meta?.llm.name ?? "…"}</div>
        <div className="font-mono text-[10.5px] text-ink-400">{meta?.llm.model}</div>
        <div className="flex items-center gap-1.5 border-t border-white/10 pt-2 text-ink-300">
          <Cpu className="h-3.5 w-3.5 text-brand-100" /> Engine: deterministic-decimal-v1
        </div>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const seg = loc.pathname.split("/")[1];
  const { meta, error } = useMeta();

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 lg:block">
        <SideNav />
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink-950/50" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-64">
            <SideNav onNavigate={() => setOpen(false)} />
            <button className="absolute right-3 top-4 text-ink-300" onClick={() => setOpen(false)} aria-label="Close menu">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-12 items-center gap-3 border-b border-ink-200 bg-white/90 px-4 backdrop-blur lg:px-6">
          <button className="rounded p-1 text-ink-600 hover:bg-ink-100 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
          <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-[13px]">
            <Link to="/" className="shrink-0 text-ink-500 hover:text-ink-900">Workbench</Link>
            {seg && CRUMBS[seg] && (
              <>
                <ChevronRight className="h-3.5 w-3.5 shrink-0 text-ink-300" />
                <span className="truncate font-medium text-ink-900">{CRUMBS[seg]}</span>
              </>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {error ? (
              <span className="rounded-full bg-risk-50 px-2 py-0.5 text-[11px] font-medium text-risk-700 ring-1 ring-risk-100">API offline</span>
            ) : (
              <Tooltip
                side="bottom"
                content={
                  meta?.llm.live
                    ? "Live LLM: used for classification, mapping suggestions, commentary and the assistant. Never for arithmetic."
                    : "No GROQ_API_KEY configured: AI features run on a deterministic offline stand-in. Set the key to enable Groq."
                }
              >
                <span
                  className={clsx(
                    "hidden items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 sm:inline-flex",
                    meta?.llm.live ? "bg-ai-50 text-ai-700 ring-ai-100" : "bg-ink-100 text-ink-600 ring-ink-200",
                  )}
                >
                  <span className={clsx("h-1.5 w-1.5 rounded-full", meta?.llm.live ? "bg-ai-600" : "bg-ink-400")} />
                  {meta?.llm.live ? `AI: ${meta.llm.model}` : "AI: offline mode"}
                </span>
              </Tooltip>
            )}
            <span className="hidden items-center gap-1.5 rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700 ring-1 ring-brand-100 md:inline-flex">
              <FunctionSquare className="h-3 w-3" /> Deterministic engine
            </span>
          </div>
        </header>
        <main className="min-w-0 flex-1">
          <ErrorBoundary resetKey={loc.pathname}>{children}</ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
