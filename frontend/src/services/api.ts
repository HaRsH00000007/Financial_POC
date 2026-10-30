import type {
  AssistantReply,
  AuditEvent,
  Commentary,
  EvalFramework,
  EvalSummary,
  EvaluationState,
  Lineage,
  Meta,
  ModelResponse,
  Workspace,
} from "@/types";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: init?.body instanceof FormData ? init?.headers : { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "Cannot reach the backend API. Is FastAPI running on port 8000?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

/** Upload with real progress events (fetch has no upload progress). */
function uploadWithProgress(file: File, onProgress: (pct: number) => void): Promise<Workspace> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);
    xhr.open("POST", `${BASE}/workspaces/upload`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      let body: any = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as Workspace);
      else reject(new ApiError(xhr.status, body?.detail ?? xhr.statusText));
    };
    xhr.onerror = () => reject(new ApiError(0, "Upload failed - is the backend running?"));
    xhr.send(form);
  });
}

export const api = {
  health: () => request<{ status: string; llm: Meta["llm"] }>("/health"),
  meta: () => request<Meta>("/meta"),
  sampleUrl: (name: string) => `${BASE}/samples/${encodeURIComponent(name)}`,

  demo: (fmt: "pdf" | "xlsx" | "csv" = "pdf") => request<Workspace>(`/workspaces/demo?fmt=${fmt}`, { method: "POST" }),
  upload: uploadWithProgress,
  workspace: (id: string) => request<Workspace>(`/workspaces/${id}`),
  updateMappings: (id: string, updates: { row_id: string; category: string | null }[]) =>
    request<Workspace>(`/workspaces/${id}/mappings`, { method: "PUT", body: JSON.stringify(updates) }),
  addResolution: (id: string, body: Record<string, unknown>) =>
    request<Workspace>(`/workspaces/${id}/resolutions`, { method: "POST", body: JSON.stringify(body) }),
  removeResolution: (id: string, resId: string) =>
    request<Workspace>(`/workspaces/${id}/resolutions/${resId}`, { method: "DELETE" }),
  calculate: (id: string) => request<ModelResponse>(`/workspaces/${id}/calculate`, { method: "POST" }),
  model: (id: string) => request<ModelResponse>(`/workspaces/${id}/model`),
  lineage: (id: string, metric: string, period: string) =>
    request<Lineage>(`/workspaces/${id}/lineage?metric=${metric}&period=${period}`),
  audit: (id: string) =>
    request<{ events: AuditEvent[]; integrity: { valid: boolean; events: number; head?: string; broken_at?: number } }>(
      `/workspaces/${id}/audit`,
    ),
  commentary: (id: string) => request<Commentary>(`/workspaces/${id}/commentary`, { method: "POST" }),
  ask: (id: string, question: string, history: { role: string; content: string }[]) =>
    request<AssistantReply>(`/workspaces/${id}/assistant`, {
      method: "POST",
      body: JSON.stringify({ question, history }),
    }),

  evalFramework: () => request<EvalFramework>("/evaluation/framework"),
  evalSummary: (s: EvaluationState) => request<EvalSummary>("/evaluation/summary", { method: "POST", body: JSON.stringify(s) }),
  evalReport: (s: EvaluationState) =>
    request<{ markdown: string; summary: EvalSummary }>("/evaluation/report", { method: "POST", body: JSON.stringify(s) }),
};
