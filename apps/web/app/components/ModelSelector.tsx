"use client";
import Link from "next/link";
import { useModel } from "./ModelContext";

// Visible model selector for the research interface. Never exposes API keys —
// key configuration lives in Settings → AI Providers.
export function ModelSelector() {
  const { settings, setSettings, providers } = useModel();
  const provider = providers.find((p) => p.provider_id === settings.provider_id);
  const models = provider?.models || [];
  const model = models.find((m: any) => m.model_id === settings.model_id);
  const hasKey = provider?.has_key;

  return (
    <div className="border border-ink-20 bg-deep p-4">
      <div className="eyebrow mb-3">AI Model</div>
      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <span className="meta block mb-1">Provider</span>
          <select
            className="field"
            value={settings.provider_id}
            onChange={(e) => {
              const p = providers.find((x) => x.provider_id === e.target.value);
              setSettings({
                provider_id: e.target.value,
                model_id: p?.default_model || p?.models?.[0]?.model_id || "",
              });
            }}
          >
            {providers.map((p) => (
              <option key={p.provider_id} value={p.provider_id}>
                {p.provider_name}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="meta block mb-1">Model</span>
          <select
            className="field"
            value={settings.model_id}
            onChange={(e) => setSettings({ model_id: e.target.value })}
          >
            {models.length === 0 && <option value="">No models listed</option>}
            {models.map((m: any) => (
              <option key={m.model_id} value={m.model_id}>
                {m.display_name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid grid-cols-2 gap-3 mt-3">
        {model?.supports_reasoning && (
          <label className="block">
            <span className="meta block mb-1">Reasoning</span>
            <select
              className="field"
              value={settings.reasoning}
              onChange={(e) => setSettings({ reasoning: e.target.value })}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </label>
        )}
        <label className="block">
          <span className="meta block mb-1">Temperature</span>
          <input
            type="number"
            step="0.1"
            min="0"
            max="2"
            className="field"
            value={settings.temperature}
            onChange={(e) => setSettings({ temperature: parseFloat(e.target.value) })}
          />
        </label>
      </div>

      <div className="flex items-center gap-4 mt-3 flex-wrap">
        <label className="meta flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={settings.archive_only}
            onChange={(e) => setSettings({ archive_only: e.target.checked })}
          />
          Archive Only
        </label>
        <span className="meta">
          Mode:{" "}
          <span className="text-wine font-medium">
            {settings.archive_only ? "Archive Only" : "Archive + Web"}
          </span>
        </span>
        <span className="ml-auto meta">
          {hasKey ? (
            <span className="text-positive">● key configured</span>
          ) : (
            <span className="text-negative">
              ● no key —{" "}
              <Link href="/settings" className="underline">
                configure
              </Link>
            </span>
          )}
        </span>
      </div>
      {model?.pricing_info && <div className="meta mt-2">{model.pricing_info}</div>}
    </div>
  );
}
