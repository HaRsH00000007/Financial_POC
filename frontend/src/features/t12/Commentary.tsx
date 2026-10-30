import { RefreshCw, ShieldCheck, ShieldX, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/Button";
import { Card, CardHeader } from "@/components/Card";
import { Callout, ErrorState, LoadingState } from "@/components/Feedback";
import { Tooltip } from "@/components/Overlay";
import { LayerTag } from "@/components/StatusBadge";
import { api } from "@/services/api";
import type { Commentary as C } from "@/types";

export function Commentary({ workspaceId, modelVersion }: { workspaceId: string; modelVersion: string }) {
  const [data, setData] = useState<C | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await api.commentary(workspaceId));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // Generate once per model version (guards React StrictMode's double effect run,
  // which would otherwise write a duplicate audit event).
  const lastKey = useRef<string | null>(null);
  useEffect(() => {
    const key = `${workspaceId}:${modelVersion}`;
    if (lastKey.current === key) return;
    lastKey.current = key;
    setData(null);
    generate();
  }, [workspaceId, modelVersion]);

  return (
    <Card className="border-ai-100">
      <CardHeader
        icon={<Sparkles className="h-4 w-4 text-ai-600" />}
        title="AI commentary"
        subtitle="AI-generated commentary based on verified financial calculations."
        actions={
          <>
            <LayerTag layer="probabilistic" />
            <Button size="sm" variant="ghost" onClick={generate} loading={busy} icon={<RefreshCw className="h-3.5 w-3.5" />}>
              Regenerate
            </Button>
          </>
        }
      />
      <div className="p-4">
        {error && <ErrorState message={error} onRetry={generate} />}
        {!data && !error && <LoadingState lines={3} className="p-0" />}
        {data && (
          <>
            <p className="text-[13.5px] leading-relaxed text-ink-800">{data.text}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-[11.5px]">
              <Tooltip content={data.numeric_check.passed ? "Every figure in the text was matched to a value produced by the deterministic engine." : `Unverified: ${data.numeric_check.unverified.join(", ")}`}>
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium ring-1 ring-inset ${data.numeric_check.passed ? "bg-ok-50 text-ok-700 ring-ok-100" : "bg-risk-50 text-risk-700 ring-risk-100"}`}
                >
                  {data.numeric_check.passed ? <ShieldCheck className="h-3.5 w-3.5" /> : <ShieldX className="h-3.5 w-3.5" />}
                  {data.numeric_check.verified}/{data.numeric_check.checked} figures verified against engine
                </span>
              </Tooltip>
              <span className="text-ink-500">
                {data.provider} · <span className="font-mono">{data.model}</span>
              </span>
            </div>
            {data.note && <Callout tone="warn" className="mt-2">{data.note}</Callout>}
            <p className="mt-3 border-t border-ink-100 pt-2 text-[11.5px] text-ink-500">{data.disclaimer}</p>
          </>
        )}
      </div>
    </Card>
  );
}
