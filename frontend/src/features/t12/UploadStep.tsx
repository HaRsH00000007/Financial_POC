import { Download, FileSpreadsheet, FileText, FlaskConical, Info, PlayCircle } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/Button";
import { Card, CardHeader } from "@/components/Card";
import { ErrorState } from "@/components/Feedback";
import { FileUploader } from "@/components/FileUploader";
import { StatusBadge } from "@/components/StatusBadge";
import { useMeta } from "@/hooks/useMeta";
import { bytes } from "@/lib/format";
import { api } from "@/services/api";
import type { Workspace } from "@/types";

type Phase = "idle" | "uploading" | "processing" | "done" | "error";

export function UploadStep({ onReady }: { onReady: (ws: Workspace) => void }) {
  const { meta } = useMeta();
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [demoFmt, setDemoFmt] = useState<"pdf" | "xlsx" | "csv">("pdf");
  const [demoBusy, setDemoBusy] = useState(false);

  const start = async (f: File) => {
    setFile(f);
    setError(null);
    setProgress(0);
    setPhase("uploading");
    try {
      const ws = await api.upload(f, (p) => {
        setProgress(p);
        if (p >= 100) setPhase("processing");
      });
      setPhase("done");
      onReady(ws);
    } catch (e: any) {
      setPhase("error");
      setError(e.message);
    }
  };

  const demo = async () => {
    setDemoBusy(true);
    setError(null);
    try {
      onReady(await api.demo(demoFmt));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setDemoBusy(false);
    }
  };

  const ext = file?.name.split(".").pop()?.toLowerCase();

  return (
    <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
      <div className="space-y-4">
        <Card>
          <CardHeader title="Upload financial document" subtitle="The document is parsed, normalized and validated before any calculation runs." />
          <div className="p-4">
            <FileUploader onFile={start} disabled={phase === "uploading" || phase === "processing"} />
            {file && (
              <div className="mt-4 rounded-lg border border-ink-200 p-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-ink-50 ring-1 ring-ink-200">
                    {ext === "pdf" ? <FileText className="h-4 w-4 text-risk-600" /> : <FileSpreadsheet className="h-4 w-4 text-ok-600" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13px] font-medium text-ink-900">{file.name}</div>
                    <div className="text-xs text-ink-500">
                      {ext?.toUpperCase()} · {bytes(file.size)}
                    </div>
                  </div>
                  {phase === "uploading" && <StatusBadge kind="PROCESSING" label={`Uploading ${progress}%`} />}
                  {phase === "processing" && <StatusBadge kind="PROCESSING" label="Extracting · normalizing · validating" />}
                  {phase === "done" && <StatusBadge kind="VALID" label="Processed" />}
                  {phase === "error" && <StatusBadge kind="ERROR" label="Failed" />}
                </div>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-ink-100">
                  <div
                    className={`h-full rounded-full transition-all ${phase === "error" ? "bg-risk-600" : phase === "processing" ? "animate-pulse bg-brand-500" : "bg-brand-500"}`}
                    style={{ width: `${phase === "idle" ? 0 : phase === "uploading" ? progress : 100}%` }}
                  />
                </div>
              </div>
            )}
            {error && (
              <div className="mt-4">
                <ErrorState title="Processing failed" message={error} onRetry={file ? () => start(file) : undefined} />
              </div>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader icon={<Info className="h-4 w-4" />} title="T-12 = Trailing Twelve Months" />
          <div className="grid gap-4 p-4 text-[13px] leading-relaxed text-ink-600 md:grid-cols-2">
            <p>
              A T-12 organizes monthly financials into a standardized model covering the <strong className="text-ink-900">latest 12 consecutive months</strong> in
              the document. It smooths seasonality and is the standard basis for underwriting, valuation and covenant testing.
            </p>
            <ul className="space-y-1.5">
              <li>• Totals are the exact sum of 12 engine-computed months (<span className="font-mono text-xs">T12_001</span>).</li>
              <li>• Margins are computed on T-12 totals, never averaged.</li>
              <li>• If 24 months are present, YoY growth compares to the prior T-12.</li>
              <li>• A missing month makes the total <strong className="text-risk-700">INCOMPLETE</strong> — never extrapolated.</li>
            </ul>
          </div>
        </Card>
      </div>

      <div className="space-y-4">
        <Card className="overflow-hidden">
          <div className="border-b border-warn-100 bg-warn-50 px-4 py-2 text-[11.5px] font-semibold tracking-wide text-warn-700">
            DEMO DATA — Not for financial decision-making
          </div>
          <div className="p-4">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-ink-950 text-white">
                <FlaskConical className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-[14px] font-semibold text-ink-950">Try Demo Dataset</h3>
                <p className="mt-0.5 text-[13px] text-ink-600">
                  24 months of monthly P&amp;L for a <em>fictional</em> manufacturer. The demo is rendered into a real document and processed by the same
                  pipeline as an upload — nothing is special-cased.
                </p>
              </div>
            </div>
            <div className="mt-4">
              <div className="label-caps mb-1.5">Built-in imperfections to review</div>
              <ul className="space-y-1 text-[12.5px] text-ink-600">
                <li className="flex gap-2"><StatusBadge kind="REVIEW_REQUIRED" size="xs" label="Review" /> A missing month in Travel &amp; Entertainment</li>
                <li className="flex gap-2"><StatusBadge kind="REVIEW_REQUIRED" size="xs" label="Review" /> A label the taxonomy cannot map</li>
                <li className="flex gap-2"><StatusBadge kind="WARNING" size="xs" /> A fuzzy-matched label to confirm</li>
                <li className="flex gap-2"><StatusBadge kind="WARNING" size="xs" /> A one-off rent spike (outlier)</li>
                <li className="flex gap-2"><StatusBadge kind="WARNING" size="xs" /> A typo in a printed subtotal</li>
              </ul>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <div className="inline-flex rounded-md border border-ink-200 p-0.5" role="radiogroup" aria-label="Demo format">
                {(["pdf", "xlsx", "csv"] as const).map((f) => (
                  <button
                    key={f}
                    role="radio"
                    aria-checked={demoFmt === f}
                    onClick={() => setDemoFmt(f)}
                    className={`rounded px-2.5 py-1 text-xs font-medium ${demoFmt === f ? "bg-ink-950 text-white" : "text-ink-600 hover:bg-ink-100"}`}
                  >
                    {f.toUpperCase()}
                  </button>
                ))}
              </div>
              <Button variant="primary" onClick={demo} loading={demoBusy} icon={<PlayCircle className="h-4 w-4" />}>
                Run demo dataset
              </Button>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Sample files" subtitle="Download and upload them yourself to exercise the upload path." />
          <ul className="divide-y divide-ink-100">
            {(meta?.samples ?? []).map((s) => (
              <li key={s} className="flex items-center justify-between gap-3 px-4 py-2.5">
                <span className="truncate font-mono text-[12px] text-ink-700">{s}</span>
                <a href={api.sampleUrl(s)} className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700">
                  <Download className="h-3.5 w-3.5" /> Download
                </a>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
