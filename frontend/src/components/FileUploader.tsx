import clsx from "clsx";
import { FileSpreadsheet, FileText, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

const DEFAULT_ACCEPT = [".pdf", ".xlsx", ".csv"];

export function FileUploader({
  onFile,
  onFiles,
  disabled,
  accept = DEFAULT_ACCEPT,
  multiple = false,
  maxMb = 20,
  maxFiles = 1,
  title = "Drop a financial document here, or",
  hint = "Monthly P&L / income statement with one column per month",
}: {
  onFile?: (f: File) => void;
  onFiles?: (f: File[]) => void;
  disabled?: boolean;
  accept?: string[];
  multiple?: boolean;
  maxMb?: number;
  maxFiles?: number;
  title?: string;
  hint?: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const take = (list: FileList | null | undefined) => {
    const files = Array.from(list ?? []).slice(0, multiple ? maxFiles : 1);
    if (!files.length) return;
    for (const f of files) {
      const ext = "." + (f.name.split(".").pop() ?? "").toLowerCase();
      if (!accept.includes(ext)) {
        setError(`Unsupported file type "${ext}". Upload ${accept.map((a) => a.slice(1).toUpperCase()).join(", ")}.`);
        return;
      }
      if (f.size > maxMb * 1024 * 1024) {
        setError(`"${f.name}" exceeds the ${maxMb} MB limit.`);
        return;
      }
    }
    setError(null);
    if (multiple) onFiles?.(files);
    else onFile?.(files[0]);
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
          if (!disabled) take(e.dataTransfer.files);
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
          {title} <span className="text-brand-600 underline-offset-2 hover:underline">browse</span>
        </p>
        <p className="mt-1 text-xs text-ink-500">{hint}</p>
        <div className="mt-4 flex items-center gap-3 text-[11px] text-ink-500">
          {accept.includes(".pdf") && <span className="inline-flex items-center gap-1"><FileText className="h-3.5 w-3.5 text-risk-600" /> PDF</span>}
          {accept.includes(".xlsx") && <span className="inline-flex items-center gap-1"><FileSpreadsheet className="h-3.5 w-3.5 text-ok-600" /> XLSX</span>}
          {accept.includes(".csv") && <span className="inline-flex items-center gap-1"><FileSpreadsheet className="h-3.5 w-3.5 text-ink-500" /> CSV</span>}
          <span className="text-ink-300">·</span>
          <span>max {maxMb} MB{multiple ? ` each · up to ${maxFiles} files` : ""}</span>
        </div>
        <input ref={input} type="file" multiple={multiple} accept={accept.join(",")} className="hidden" onChange={(e) => take(e.target.files)} />
      </div>
      {error && <p className="mt-2 text-xs text-risk-700">{error}</p>}
    </div>
  );
}
