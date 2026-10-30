import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "@/services/api";
import type { Meta } from "@/types";

interface MetaState {
  meta: Meta | null;
  error: string | null;
  reload: () => void;
}

const Ctx = createContext<MetaState>({ meta: null, error: null, reload: () => {} });

export function MetaProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setError(null);
    api.meta().then(setMeta, (e) => setError(e.message));
  };
  useEffect(load, []);
  return <Ctx.Provider value={{ meta, error, reload: load }}>{children}</Ctx.Provider>;
}

export const useMeta = () => useContext(Ctx);
