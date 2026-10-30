import clsx from "clsx";
import { FileSpreadsheet, FileText, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

const ACCEPT = [".pdf", ".xlsx", ".csv"];

export function FileUploader({ onFile, disabled }: { onFile: (f: File) => void; disabled?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const take = (f: File | undefined) => {
    if (!f) return;
    const ext = "." + (f.name.split(".").pop() ?? "").toLowerCase();
    if (!ACCEPT.includes(ext)) {
      setError(`Unsupported file type "${ext}". Upload a PDF, XLSX or CSV.`);
      return;
    }
    if (f.size > 20 * 1024 * 1024) {
      setError("File exceeds the 20 MB POC limit.");
      return;
    }
    setError(null);
    onFile(f);
  };

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-disabled={disabled}
        onClick={() => !disabled && input.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && !disabled && input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (!disabled) take(e.dataTransfer.files[0]);
        }}
        className={clsx(
          "flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-6 py-10 text-center transition-colors",
          drag ? "border-brand-500 bg-brand-50" : "border-ink-300 bg-ink-50/60 hover:border-ink-400 hover:bg-ink-50",
          disabled && "pointer-events-none opacity-60",
        )}
      >
        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg border border-ink-200 bg-white text-ink-600 shadow-sm">
          <UploadCloud className="h-5 w-5" />
        </div>
        <p className="text-sm font-medium text-ink-900">
          Drop a financial document here, or <span className="text-brand-600 underline-offset-2 hover:underline">browse</span>
        </p>
        <p className="mt-1 text-xs text-ink-500">Monthly P&amp;L / income statement with one column per month</p>
        <div className="mt-4 flex items-center gap-3 text-[11px] text-ink-500">
          <span className="inline-flex items-center gap-1"><FileText className="h-3.5 w-3.5 text-risk-600" /> PDF</span>
          <span className="inline-flex items-center gap-1"><FileSpreadsheet className="h-3.5 w-3.5 text-ok-600" /> XLSX</span>
          <span className="inline-flex items-center gap-1"><FileSpreadsheet className="h-3.5 w-3.5 text-ink-500" /> CSV</span>
          <span className="text-ink-300">·</span>
          <span>max 20 MB</span>
        </div>
        <input ref={input} type="file" accept={ACCEPT.join(",")} className="hidden" onChange={(e) => take(e.target.files?.[0])} />
      </div>
      {error && <p className="mt-2 text-xs text-risk-700">{error}</p>}
    </div>
  );
}
