"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { api } from "../lib/api";

export type ModelSettings = {
  provider_id: string;
  model_id: string;
  reasoning: string;
  temperature: number;
  archive_only: boolean;
  citation_strictness: string;
};

const DEFAULTS: ModelSettings = {
  provider_id: "groq",
  model_id: "openai/gpt-oss-120b",
  reasoning: "medium",
  temperature: 0.2,
  archive_only: true,
  citation_strictness: "strict",
};

type Ctx = {
  settings: ModelSettings;
  setSettings: (s: Partial<ModelSettings>) => void;
  providers: any[];
  reloadProviders: () => void;
};

const ModelCtx = createContext<Ctx | null>(null);

export function ModelProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettingsState] = useState<ModelSettings>(DEFAULTS);
  const [providers, setProviders] = useState<any[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("tai.model");
      if (raw) setSettingsState({ ...DEFAULTS, ...JSON.parse(raw) });
    } catch {}
    reloadProviders();
  }, []);

  const setSettings = (s: Partial<ModelSettings>) => {
    setSettingsState((prev) => {
      const next = { ...prev, ...s };
      try {
        localStorage.setItem("tai.model", JSON.stringify(next));
      } catch {}
      return next;
    });
  };

  const reloadProviders = () => {
    api.providers().then((r) => setProviders(r.providers || [])).catch(() => setProviders([]));
  };

  return (
    <ModelCtx.Provider value={{ settings, setSettings, providers, reloadProviders }}>
      {children}
    </ModelCtx.Provider>
  );
}

export function useModel() {
  const ctx = useContext(ModelCtx);
  if (!ctx) throw new Error("useModel must be used within ModelProvider");
  return ctx;
}
