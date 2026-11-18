import { BookOpenText, FileText, LockKeyhole, Search, Trash2, Upload } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/Button";
import { Card, CardHeader } from "@/components/Card";
import { ErrorState } from "@/components/Feedback";
import { FileUploader } from "@/components/FileUploader";
import { StatusBadge } from "@/components/StatusBadge";
import { bytes } from "@/lib/format";
import { api } from "@/services/api";
import type { Workspace } from "@/types";

type Phase = "idle" | "uploading" | "processing" | "error";

export function AnnualUpload({ onReady }: { onReady: (ws: Workspace) => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const busy = phase === "uploading" || phase === "processing";

  const add = (fs: File[]) => {
    const names = new Set(files.map((f) => f.name));
    setFiles([...files, ...fs.filter((f) => !names.has(f.name))].slice(0, 5));
  };

  const start = async () => {
    setError(null);
    setProgress(0);
    setPhase("uploading");
    try {
      const ws = await api.uploadAnnual(files, (p) => {
        setProgress(p);
        if (p >= 100) setPhase("processing");
      });
      setPhase("idle");
      onReady(ws);
    } catch (e: any) {
      setPhase("error");
      setError(e.message);
    }
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
      <div className="space-y-4">
        <Card>
          <CardHeader
            title="Upload annual reports"
            subtitle="One or more annual reports of the same company (e.g. three consecutive years). Statements are located, parsed and reconciled before any calculation runs."
          />
          <div className="p-4">
            <FileUploader
              multiple
              maxFiles={5}
              maxMb={40}
              accept={[".pdf"]}
              onFiles={add}
              disabled={busy}
              title="Drop annual report PDFs here, or"
              hint="Integrated / annual reports with consolidated financial statements"
            />
            {files.length > 0 && (
              <ul className="mt-4 divide-y divide-ink-100 rounded-lg border border-ink-200">
                {files.map((f) => (
                  <li key={f.name} className="flex items-center gap-3 px-3 py-2.5">
                    <FileText className="h-4 w-4 shrink-0 text-risk-600" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[13px] font-medium text-ink-900">{f.name}</div>
                      <div className="text-xs text-ink-500">PDF · {bytes(f.size)}</div>
                    </div>
                    {!busy && (
                      <button className="rounded p-1 text-ink-400 hover:bg-risk-50 hover:text-risk-700" aria-label={`Remove ${f.name}`} onClick={() => setFiles(files.filter((x) => x !== f))}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {files.length > 0 && (
              <div className="mt-3">
                <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-ink-100">
                  <div
                    className={`h-full rounded-full transition-all ${phase === "error" ? "bg-risk-600" : phase === "processing" ? "animate-pulse bg-brand-500" : "bg-brand-500"}`}
                    style={{ width: `${phase === "idle" ? 0 : phase === "uploading" ? progress : 100}%` }}
                  />
                </div>
                <div className="flex items-center justify-between gap-3">
                  {phase === "uploading" && <StatusBadge kind="PROCESSING" label={`Uploading ${progress}%`} />}
                  {phase === "processing" && <StatusBadge kind="PROCESSING" label="Indexing · locating statements · parsing · reconciling" />}
                  {(phase === "idle" || phase === "error") && <span className="text-xs text-ink-500">{files.length} report(s) selected</span>}
                  <Button variant="primary" onClick={start} loading={busy} disabled={!files.length} icon={<Upload className="h-4 w-4" />}>
                    Process {files.length > 1 ? `${files.length} reports` : "report"}
                  </Button>
                </div>
              </div>
            )}
            {error && (
              <div className="mt-4">
                <ErrorState title="Processing failed" message={error} onRetry={files.length ? start : undefined} />
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader icon={<BookOpenText className="h-4 w-4" />} title="How annual reports are processed" />
          <ol className="space-y-2.5 p-4 text-[13px] leading-relaxed text-ink-600">
            <li><strong className="text-ink-900">1. Index.</strong> Every page is chunked into a retrieval (RAG) index. Nothing is sent to an AI model.</li>
            <li><strong className="text-ink-900">2. Locate.</strong> Structural markers find the consolidated Balance Sheet, P&amp;L and Cash Flow among 150+ pages.</li>
            <li><strong className="text-ink-900">3. Parse &amp; verify.</strong> A deterministic parser reads each line with its page reference; accounting identities prove the extraction is complete.</li>
            <li><strong className="text-ink-900">4. Multi-year model.</strong> Overlapping years are taken from the latest report; restated comparatives are flagged.</li>
            <li><strong className="text-ink-900">5. Insights.</strong> The AI sees an <em>Insight Brief</em> (engine figures + a few retrieved passages + external context), never the full report.</li>
          </ol>
        </Card>
        <Card className="p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-ink-950 text-white">
              <LockKeyhole className="h-4 w-4" />
            </div>
            <div className="text-[13px] leading-relaxed text-ink-600">
              <div className="font-semibold text-ink-950">AI exposure ledger</div>
              Every time report content is sent to a language model, the pages, chunks and character count are logged and shown in the
              <em> AI Context</em> tab. In offline mode nothing leaves the platform.
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs text-ink-500">
            <Search className="h-3.5 w-3.5" /> Retrieval: BM25 (lexical, runs locally)
          </div>
        </Card>
      </div>
    </div>
  );
}
