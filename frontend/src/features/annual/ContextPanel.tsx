import { Globe2, LockKeyhole, Plus, Search, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { Card, CardHeader } from "@/components/Card";
import { Callout, ErrorState, LoadingState } from "@/components/Feedback";
import { StatusBadge } from "@/components/StatusBadge";
import { periodLabel, time } from "@/lib/format";
import { api } from "@/services/api";
import type { Exposure, InsightBrief, Passage, Workspace } from "@/types";

/** Everything that can reach the AI layer: the Insight Brief, the exposure ledger, external context and retrieval. */
export function ContextPanel({ ws, setWs }: { ws: Workspace; setWs: (w: Workspace) => void }) {
  const [data, setData] = useState<{ brief: InsightBrief; exposure: Exposure } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.brief(ws.id).then(setData, (e) => setError(e.message));
  useEffect(() => {
    load();
  }, [ws.id, ws.external?.length]);

  return (
    <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
      <div className="space-y-4">
        <Card>
          <CardHeader
            icon={<LockKeyhole className="h-4 w-4" />}
            title="Insight Brief — exactly what the insight model sees"
            subtitle="Built deterministically from the engine, the validation results, a few retrieved passages and external facts."
          />
          {error && <div className="p-4"><ErrorState message={error} /></div>}
          {!data && !error && <LoadingState lines={6} />}
          {data && <BriefView brief={data.brief} />}
        </Card>
        <ExternalCard ws={ws} setWs={setWs} />
      </div>
      <div className="space-y-4">
        {data && <ExposureCard exposure={data.exposure} />}
        <SearchCard wsId={ws.id} />
      </div>
    </div>
  );
}

function BriefView({ brief }: { brief: InsightBrief }) {
  return (
    <div className="space-y-4 p-4">
      <section>
        <div className="label-caps mb-1.5">Engine facts (F) · {periodLabel(brief.latest)} vs {brief.prior ? periodLabel(brief.prior) : "—"}</div>
        <div className="scroll-thin max-h-72 overflow-auto rounded-md border border-ink-200">
          <table className="w-full text-xs">
            <tbody className="divide-y divide-ink-100">
              {brief.facts.map((f) => (
                <tr key={f.id}>
                  <td className="px-2 py-1 font-mono text-[10.5px] text-brand-700">{f.id}</td>
                  <td className="px-2 py-1 text-ink-800">{f.name}</td>
                  <td className="px-2 py-1 text-ink-500">{periodLabel(f.period, true)}</td>
                  <td className="num px-2 py-1 text-right text-ink-900">{f.display}</td>
                  <td className="px-2 py-1 font-mono text-[10.5px] text-ink-400">{f.formula_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section>
        <div className="label-caps mb-1.5">Data quality (Q)</div>
        <ul className="space-y-1 text-xs text-ink-700">
          {brief.quality.map((q) => (
            <li key={q.id}><span className="mr-1.5 font-mono text-ok-700">{q.id}</span>{q.text}</li>
          ))}
        </ul>
      </section>
      <section>
        <div className="label-caps mb-1.5">Retrieved report passages (N) · {brief.narrative.length}</div>
        {brief.narrative.length === 0 && <p className="text-xs text-ink-500">None — narrative passages are excluded from this brief.</p>}
        <ul className="space-y-2">
          {brief.narrative.map((n) => (
            <li key={n.id} className="rounded-md border border-ai-100 bg-ai-50/40 p-2 text-xs text-ink-700">
              <div className="mb-0.5 flex items-center gap-2 text-[11px] text-ai-700">
                <span className="font-mono">{n.id}</span> {n.topic.replace(/_/g, " ")} · {n.document} p.{n.page}
              </div>
              {n.text}
            </li>
          ))}
        </ul>
      </section>
      <section>
        <div className="label-caps mb-1.5">External context (X) · {brief.external.length}</div>
        {brief.external.length === 0 && <p className="text-xs text-ink-500">No external facts added.</p>}
        <ul className="space-y-1 text-xs text-ink-700">
          {brief.external.map((x) => (
            <li key={x.id}><span className="mr-1.5 font-mono text-warn-700">{x.id}</span>{x.text} <span className="text-ink-400">— {x.source}{x.as_of ? `, ${x.as_of}` : ""}</span></li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function ExposureCard({ exposure }: { exposure: Exposure }) {
  return (
    <Card>
      <CardHeader icon={<ShieldCheck className="h-4 w-4" />} title="AI exposure ledger" subtitle="Every transfer of report content to a hosted LLM" />
      <div className="grid grid-cols-2 gap-px border-b border-ink-100 bg-ink-100">
        <div className="bg-white px-4 py-3">
          <div className="label-caps">Pages shared</div>
          <div className="num mt-1 text-[17px] font-semibold text-ink-950">{exposure.pages_shared} / {exposure.pages_total}</div>
        </div>
        <div className="bg-white px-4 py-3">
          <div className="label-caps">Characters shared</div>
          <div className="num mt-1 text-[17px] font-semibold text-ink-950">{exposure.chars_shared.toLocaleString()}</div>
          <div className="text-[11px] text-ink-500">of {exposure.report_chars_total.toLocaleString()} in the reports</div>
        </div>
      </div>
      {!exposure.provider_live && (
        <div className="p-4">
          <Callout tone="brand">Offline mode: no content has left the platform. With a Groq key, each transfer is listed here with its pages and size.</Callout>
        </div>
      )}
      {exposure.ledger.length > 0 && (
        <ul className="divide-y divide-ink-100">
          {[...exposure.ledger].reverse().map((e, i) => (
            <li key={i} className="px-4 py-2.5 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-ink-900">{e.purpose}</span>
                <span className="text-ink-400">{time(e.at)}</span>
              </div>
              <div className="text-ink-500">
                {e.provider} · {e.model} · {e.chars.toLocaleString()} chars{e.pages.length ? ` · pages ${e.pages.map((p) => p.page).join(", ")}` : ""}
              </div>
              <div className="mt-1 line-clamp-2 font-mono text-[10.5px] text-ink-400">{e.preview}</div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function ExternalCard({ ws, setWs }: { ws: Workspace; setWs: (w: Workspace) => void }) {
  const [text, setText] = useState("");
  const [source, setSource] = useState("");
  const [asOf, setAsOf] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const add = async () => {
    setBusy(true);
    setErr(null);
    try {
      setWs(await api.addExternal(ws.id, [{ text, source, as_of: asOf }]));
      setText("");
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader icon={<Globe2 className="h-4 w-4" />} title="External context" subtitle="Market / private-company intelligence for the insights. Never used in calculations." />
      <ul className="divide-y divide-ink-100">
        {(ws.external_providers ?? []).map((p) => (
          <li key={p.key} className="flex items-start gap-3 px-4 py-2.5 text-xs">
            <StatusBadge kind={p.connected ? "VALID" : "NEUTRAL"} size="xs" label={p.connected ? "Connected" : "Not connected"} />
            <div>
              <div className="font-medium text-ink-900">{p.name}</div>
              <div className="text-ink-500">{p.detail}</div>
            </div>
          </li>
        ))}
      </ul>
      <div className="space-y-2 border-t border-ink-100 p-4">
        <textarea className="input min-h-[64px]" placeholder="Fact, e.g. a funding round, competitor move or market share figure (copied from Tracxn or another source)" value={text} onChange={(e) => setText(e.target.value)} />
        <div className="grid gap-2 sm:grid-cols-[1fr_140px_auto]">
          <input className="input" placeholder="Source (required), e.g. Tracxn export" value={source} onChange={(e) => setSource(e.target.value)} />
          <input className="input" placeholder="As of (e.g. 2026-10)" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
          <Button loading={busy} disabled={!text.trim() || !source.trim()} onClick={add} icon={<Plus className="h-3.5 w-3.5" />}>
            Add
          </Button>
        </div>
        {err && <p className="text-xs text-risk-700">{err}</p>}
      </div>
      {(ws.external ?? []).length > 0 && (
        <ul className="divide-y divide-ink-100 border-t border-ink-100">
          {ws.external!.map((x) => (
            <li key={x.id} className="flex items-start gap-2 px-4 py-2.5 text-xs">
              <span className="font-mono text-warn-700">{x.id}</span>
              <div className="min-w-0 flex-1">
                <div className="text-ink-800">{x.text}</div>
                <div className="text-ink-500">{x.source}{x.as_of ? ` · ${x.as_of}` : ""}</div>
              </div>
              <button className="rounded p-1 text-ink-400 hover:bg-risk-50 hover:text-risk-700" aria-label="Remove fact" onClick={async () => setWs(await api.removeExternal(ws.id, x.id))}>
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function SearchCard({ wsId }: { wsId: string }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Passage[] | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    if (!q.trim()) return;
    setBusy(true);
    try {
      setHits((await api.search(wsId, q, 5)).passages);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <CardHeader icon={<Search className="h-4 w-4" />} title="Search the reports" subtitle="BM25 retrieval over every page — runs locally, nothing is sent to an AI model" />
      <form
        className="flex gap-2 p-4"
        onSubmit={(e) => {
          e.preventDefault();
          run();
        }}
      >
        <input className="input" placeholder="e.g. Jio ARPU, new energy capex, dividend" value={q} onChange={(e) => setQ(e.target.value)} />
        <Button type="submit" loading={busy}>Search</Button>
      </form>
      {hits && (
        <ul className="divide-y divide-ink-100 border-t border-ink-100">
          {hits.length === 0 && <li className="px-4 py-3 text-xs text-ink-500">No matching passages.</li>}
          {hits.map((h) => (
            <li key={h.chunk_id} className="px-4 py-2.5 text-xs">
              <div className="mb-0.5 text-[11px] text-ink-500">
                {h.document} · p.{h.page} · {h.kind} · score {h.score}
              </div>
              <div className="text-ink-700">{h.text}</div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
