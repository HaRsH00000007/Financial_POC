import clsx from "clsx";
import { ChevronRight, Link2, ShieldCheck, ShieldX } from "lucide-react";
import { useEffect, useState } from "react";
import { Card, CardHeader } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/Feedback";
import { time } from "@/lib/format";
import { api } from "@/services/api";
import type { AuditEvent } from "@/types";

const ACTOR: Record<AuditEvent["actor"], string> = {
  system: "bg-ink-100 text-ink-700",
  ai: "bg-ai-50 text-ai-700",
  user: "bg-warn-50 text-warn-700",
  engine: "bg-brand-50 text-brand-700",
};

export function AuditLogView({ workspaceId, refreshKey }: { workspaceId: string; refreshKey: unknown }) {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.audit>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [actor, setActor] = useState<string>("all");

  useEffect(() => {
    api.audit(workspaceId).then(setData, (e) => setError(e.message));
  }, [workspaceId, refreshKey]);

  if (error) return <ErrorState message={error} />;
  if (!data) return <Card><LoadingState lines={6} /></Card>;
  const events = [...data.events].reverse().filter((e) => actor === "all" || e.actor === actor);

  return (
    <Card>
      <CardHeader
        title="Immutable audit log"
        subtitle="Append-only; every event stores the SHA-256 of the previous event, so edits or deletions break the chain."
        actions={
          <span className={clsx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11.5px] font-medium ring-1 ring-inset", data.integrity.valid ? "bg-ok-50 text-ok-700 ring-ok-100" : "bg-risk-50 text-risk-700 ring-risk-100")}>
            {data.integrity.valid ? <ShieldCheck className="h-3.5 w-3.5" /> : <ShieldX className="h-3.5 w-3.5" />}
            {data.integrity.valid ? `Chain verified · ${data.integrity.events} events` : `Chain broken at #${data.integrity.broken_at}`}
          </span>
        }
      />
      <div className="flex flex-wrap gap-1.5 border-b border-ink-100 px-4 py-2">
        {["all", "system", "ai", "engine", "user"].map((a) => (
          <button key={a} onClick={() => setActor(a)} className={clsx("rounded-full px-2.5 py-1 text-xs font-medium capitalize", actor === a ? "bg-ink-950 text-white" : "bg-ink-100 text-ink-600 hover:bg-ink-200")}>
            {a === "user" ? "human" : a}
          </button>
        ))}
        {data.integrity.head && <span className="ml-auto self-center font-mono text-[10.5px] text-ink-400">head {data.integrity.head.slice(0, 16)}…</span>}
      </div>
      <ul className="divide-y divide-ink-100">
        {events.map((e) => (
          <li key={e.seq}>
            <button className="flex w-full items-start gap-3 px-4 py-2.5 text-left hover:bg-ink-50" onClick={() => setOpen(open === e.seq ? null : e.seq)}>
              <span className="num w-8 shrink-0 pt-0.5 text-right font-mono text-[11px] text-ink-400">#{e.seq}</span>
              <span className={clsx("mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10.5px] font-semibold uppercase", ACTOR[e.actor])}>{e.actor === "user" ? "human" : e.actor}</span>
              <div className="min-w-0 flex-1">
                <div className="text-[13px] text-ink-900">{e.summary}</div>
                <div className="text-[11.5px] text-ink-500">
                  <span className="font-mono">{e.event_type}</span> · {e.agent ?? "—"} · {time(e.timestamp)}
                </div>
              </div>
              <span className="hidden items-center gap-1 pt-0.5 font-mono text-[10.5px] text-ink-400 md:inline-flex">
                <Link2 className="h-3 w-3" />
                {e.hash.slice(0, 10)}
              </span>
              <ChevronRight className={clsx("mt-0.5 h-4 w-4 text-ink-400 transition-transform", open === e.seq && "rotate-90")} />
            </button>
            {open === e.seq && (
              <div className="bg-ink-50 px-4 py-3 pl-[60px]">
                <div className="mb-1 font-mono text-[10.5px] text-ink-500">prev {e.prev_hash.slice(0, 24)}… → hash {e.hash.slice(0, 24)}…</div>
                <pre className="scroll-thin max-h-64 overflow-auto rounded-md bg-white p-2.5 font-mono text-[11px] text-ink-700 ring-1 ring-ink-200">{JSON.stringify(e.details, null, 2)}</pre>
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
