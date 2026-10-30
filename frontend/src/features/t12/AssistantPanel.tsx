import clsx from "clsx";
import { ChevronRight, Send, ShieldCheck, ShieldX, Sparkles, Wrench, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Markdown } from "@/components/Markdown";
import { api } from "@/services/api";
import type { AssistantReply } from "@/types";

const SUGGESTIONS = [
  "What was our highest revenue month?",
  "Why did EBITDA change?",
  "Show me the calculation for EBITDA",
  "What expenses increased the most?",
  "Give me a management summary",
  "Which numbers require review?",
];

interface Msg {
  role: "user" | "assistant";
  content: string;
  reply?: AssistantReply;
  error?: boolean;
}

export function AssistantPanel({ workspaceId, onClose }: { workspaceId: string; onClose: () => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, busy]);

  const ask = async (q: string) => {
    if (!q.trim() || busy) return;
    const history = msgs.filter((m) => !m.error).map((m) => ({ role: m.role, content: m.content }));
    setMsgs((m) => [...m, { role: "user", content: q }]);
    setInput("");
    setBusy(true);
    try {
      const reply = await api.ask(workspaceId, q, history);
      setMsgs((m) => [...m, { role: "assistant", content: reply.answer, reply }]);
    } catch (e: any) {
      setMsgs((m) => [...m, { role: "assistant", content: e.message, error: true }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex items-center justify-between border-b border-ink-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-ai-600 text-white">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <div className="text-[13px] font-semibold text-ink-950">Finance assistant</div>
            <div className="text-[11px] text-ink-500">Answers via deterministic tools · never computes</div>
          </div>
        </div>
        <button onClick={onClose} className="rounded p-1 text-ink-500 hover:bg-ink-100" aria-label="Close assistant">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="scroll-thin flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {msgs.length === 0 && (
          <div>
            <div className="rounded-lg border border-ink-200 bg-ink-50 p-3 text-xs leading-relaxed text-ink-600">
              <div className="mb-1 font-semibold text-ink-800">How this works</div>
              LLM → calls deterministic data &amp; calculation functions → receives verified results → explains them. Every figure in an answer is checked against the
              tool results before it is shown.
            </div>
            <div className="label-caps mb-2 mt-4">Try asking</div>
            <div className="flex flex-col gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => ask(s)} className="rounded-md border border-ink-200 px-3 py-2 text-left text-[13px] text-ink-700 hover:border-ai-600/40 hover:bg-ai-50">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="ml-8 rounded-lg bg-ink-950 px-3 py-2 text-[13px] text-white">{m.content}</div>
          ) : (
            <div key={i} className={clsx("mr-2 text-[13px] leading-relaxed text-ink-800", m.error && "text-risk-700")}>
              {m.error ? m.content : <Markdown text={m.content} />}
              {m.reply && <ReplyMeta reply={m.reply} />}
            </div>
          ),
        )}
        {busy && (
          <div className="flex items-center gap-2 text-xs text-ink-500">
            <span className="flex gap-1">
              {[0, 1, 2].map((d) => (
                <span key={d} className="h-1.5 w-1.5 animate-bounce rounded-full bg-ai-600" style={{ animationDelay: `${d * 120}ms` }} />
              ))}
            </span>
            Calling deterministic tools…
          </div>
        )}
        <div ref={end} />
      </div>

      <form
        className="border-t border-ink-100 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
      >
        <div className="flex items-center gap-2">
          <input className="input" placeholder="Ask about the T-12 model…" value={input} onChange={(e) => setInput(e.target.value)} disabled={busy} />
          <button type="submit" disabled={busy || !input.trim()} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-ai-600 text-white disabled:opacity-40" aria-label="Send">
            <Send className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-1.5 text-[10.5px] text-ink-400">AI-generated content should be reviewed before use in formal financial reporting.</p>
      </form>
    </div>
  );
}

function ReplyMeta({ reply }: { reply: AssistantReply }) {
  const [open, setOpen] = useState(false);
  const nc = reply.numeric_check;
  return (
    <div className="mt-2 rounded-md border border-ink-200 bg-ink-50/60 text-[11px]">
      <button className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-ink-600" onClick={() => setOpen(!open)}>
        <Wrench className="h-3 w-3" />
        {reply.tool_calls.length} deterministic tool call{reply.tool_calls.length === 1 ? "" : "s"}
        <span className={clsx("ml-auto inline-flex items-center gap-1 font-medium", nc.passed ? "text-ok-700" : "text-risk-700")}>
          {nc.passed ? <ShieldCheck className="h-3 w-3" /> : <ShieldX className="h-3 w-3" />}
          {nc.checked ? `${nc.verified}/${nc.checked} figures verified` : "no figures"}
        </span>
        <ChevronRight className={clsx("h-3 w-3 transition-transform", open && "rotate-90")} />
      </button>
      {open && (
        <div className="space-y-1 border-t border-ink-200 px-2.5 py-2 font-mono text-[10.5px] text-ink-600">
          {reply.tool_calls.map((t, i) => (
            <div key={i}>
              {t.tool}({Object.entries(t.args ?? {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})
            </div>
          ))}
          <div className="pt-1 font-sans text-ink-400">Provider: {reply.provider}</div>
          {reply.note && <div className="font-sans text-warn-700">{reply.note}</div>}
        </div>
      )}
    </div>
  );
}
