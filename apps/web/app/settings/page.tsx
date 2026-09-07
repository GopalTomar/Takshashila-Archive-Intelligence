"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { PageHeader } from "../components/Shell";
import { useModel } from "../components/ModelContext";
import { ErrorNote, Loading } from "../components/ui";

export default function Settings() {
  const [tab, setTab] = useState("providers");
  const tabs = [
    ["providers", "AI Providers"],
    ["retrieval", "Retrieval"],
    ["sources", "Archive Sources"],
    ["processing", "Processing / Demo"],
    ["system", "System"],
  ];
  return (
    <div>
      <PageHeader eyebrow="Settings" title="Settings" />
      <div className="flex gap-2 px-10 py-4 rule flex-wrap">
        {tabs.map(([k, l]) => (
          <button key={k} className={tab === k ? "btn" : "btn-ghost"} onClick={() => setTab(k)}>
            {l}
          </button>
        ))}
      </div>
      <div className="px-10 py-8">
        {tab === "providers" && <Providers />}
        {tab === "retrieval" && <Retrieval />}
        {tab === "sources" && <Sources />}
        {tab === "processing" && <Processing />}
        {tab === "system" && <System />}
      </div>
    </div>
  );
}

function Providers() {
  const { providers, reloadProviders } = useModel();
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [urls, setUrls] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<Record<string, string>>({});

  async function saveKey(id: string) {
    try {
      await api.setProviderKey(id, { api_key: keys[id], base_url: urls[id] || undefined });
      setMsg({ ...msg, [id]: "Key saved (stored encrypted, never returned)." });
      setKeys({ ...keys, [id]: "" });
      reloadProviders();
    } catch (e: any) {
      setMsg({ ...msg, [id]: `Error: ${e.message}` });
    }
  }
  async function test(id: string) {
    setMsg({ ...msg, [id]: "Testing…" });
    try {
      const r = await api.testProvider(id);
      setMsg({ ...msg, [id]: r.ok ? `Connection ok (${r.models_seen ?? "?"} models).` : `Failed: ${r.detail}` });
      reloadProviders();
    } catch (e: any) {
      setMsg({ ...msg, [id]: `Error: ${e.message}` });
    }
  }
  async function refresh(id: string) {
    try {
      const r = await api.refreshModels(id);
      setMsg({ ...msg, [id]: `Fetched ${r.live_models} live models (${r.added} new).` });
      reloadProviders();
    } catch (e: any) {
      setMsg({ ...msg, [id]: `Error: ${e.message}` });
    }
  }

  return (
    <div className="space-y-6">
      <div className="meta">
        API keys are stored encrypted on the server and are never returned to the browser, logged,
        or included in errors. The connection test makes a real request to the provider.
      </div>
      {providers.map((p) => (
        <div key={p.provider_id} className="card">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[20px]">{p.provider_name}</div>
              <div className="meta mt-1">
                {p.has_key ? `key ${p.key_hint} · ` : "no key · "}
                availability: {p.availability_status}
              </div>
            </div>
            <div className="flex gap-2">
              <button className="btn-ghost" onClick={() => test(p.provider_id)}>Test Connection</button>
              <button className="btn-ghost" onClick={() => refresh(p.provider_id)}>Refresh Models</button>
            </div>
          </div>
          <div className="grid md:grid-cols-2 gap-3 mt-4">
            <input
              className="field"
              type="password"
              placeholder="API key (paste to set)"
              value={keys[p.provider_id] || ""}
              onChange={(e) => setKeys({ ...keys, [p.provider_id]: e.target.value })}
            />
            <input
              className="field"
              placeholder={p.base_url || "Base URL (optional)"}
              value={urls[p.provider_id] || ""}
              onChange={(e) => setUrls({ ...urls, [p.provider_id]: e.target.value })}
            />
          </div>
          <div className="flex gap-2 mt-3">
            <button className="btn" onClick={() => saveKey(p.provider_id)} disabled={!keys[p.provider_id]}>
              Save Key
            </button>
            {p.has_key && (
              <button
                className="btn-ghost"
                onClick={() => api.deleteProviderKey(p.provider_id).then(reloadProviders)}
              >
                Remove Key
              </button>
            )}
          </div>
          {msg[p.provider_id] && <div className="meta mt-2">{msg[p.provider_id]}</div>}
          {p.models?.length > 0 && (
            <div className="mt-4">
              <div className="eyebrow mb-2">Models</div>
              <div className="flex flex-wrap gap-2">
                {p.models.map((m: any) => (
                  <span key={m.model_id} className="chip" title={m.pricing_info || ""}>
                    {m.display_name}
                    {m.supports_reasoning ? " · reasoning" : ""}
                    {m.is_embedding ? " · embeddings" : ""}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function Retrieval() {
  const [s, setS] = useState<any>(null);
  const [msg, setMsg] = useState("");
  useEffect(() => {
    api.retrievalSettings().then(setS).catch(() => setS({}));
  }, []);
  if (!s) return <Loading />;
  return (
    <div className="card max-w-xl">
      <div className="eyebrow mb-3">Retrieval defaults</div>
      {[
        ["chunk_target_chars", "Chunk size (chars)"],
        ["chunk_overlap_chars", "Overlap (chars)"],
        ["top_k", "Top K"],
        ["hybrid_weight", "Hybrid weight (0 kw – 1 semantic)"],
      ].map(([k, label]) => (
        <label key={k} className="block mb-3">
          <span className="meta block mb-1">{label}</span>
          <input
            className="field"
            type="number"
            step={k === "hybrid_weight" ? "0.1" : "1"}
            value={s[k] ?? ""}
            onChange={(e) => setS({ ...s, [k]: parseFloat(e.target.value) })}
          />
        </label>
      ))}
      <button className="btn" onClick={() => api.setRetrievalSettings(s).then(() => setMsg("Saved."))}>
        Save
      </button>
      {msg && <span className="meta ml-3">{msg}</span>}
    </div>
  );
}

function Sources() {
  const [sources, setSources] = useState<any[] | null>(null);
  useEffect(() => {
    api.sources().then((r) => setSources(r.sources)).catch(() => setSources([]));
  }, []);
  if (!sources) return <Loading />;
  return (
    <div className="space-y-4">
      <div className="meta">
        Sources are defined in <code>config/sources.yaml</code>. Seed URLs must be verified public URLs.
      </div>
      {sources.map((s) => (
        <div key={s.id} className="card">
          <div className="text-[18px]">{s.name}</div>
          <div className="meta mt-1">
            id: {s.id} · {s.seed_url_count} seed URLs · domains: {(s.allowed_domains || []).join(", ") || "none"}
          </div>
          <div className="text-[13px] text-ink-70 mt-2">{s.notes}</div>
        </div>
      ))}
    </div>
  );
}

function Processing() {
  const [msg, setMsg] = useState("");
  const [embStatus, setEmbStatus] = useState<any>(null);
  useEffect(() => {
    api.embeddingsStatus().then(setEmbStatus).catch(() => {});
  }, []);
  return (
    <div className="space-y-6">
      <div className="card">
        <div className="eyebrow mb-2">Embeddings</div>
        {embStatus ? (
          <div className="text-[14px]">
            Provider: <b>{embStatus.provider}</b> · enabled: {String(embStatus.enabled)} · real semantic:{" "}
            {String(embStatus.is_real_semantic)}
            <div className="meta mt-1">{embStatus.detail}</div>
          </div>
        ) : (
          <Loading />
        )}
      </div>
      <div className="card">
        <div className="eyebrow mb-2">Demo data</div>
        <div className="meta mb-3">
          Synthetic sample documents, clearly labelled "DEMO DATA — NOT ARCHIVAL MATERIAL" and kept
          separate from production records.
        </div>
        <div className="flex gap-2">
          <button className="btn" onClick={() => api.seedDemo().then((r) => setMsg(`Seeded: ${r.seeded.join(", ")}`))}>
            Seed Demo Data
          </button>
          <button className="btn-ghost" onClick={() => api.clearDemo().then((r) => setMsg(`Cleared ${r.cleared} demo docs`))}>
            Clear Demo Data
          </button>
        </div>
        {msg && <div className="meta mt-2">{msg}</div>}
      </div>
    </div>
  );
}

function System() {
  const [sys, setSys] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.system().then(setSys).catch((e) => setErr(e.message));
  }, []);
  if (err) return <ErrorNote message={err} />;
  if (!sys) return <Loading />;
  return (
    <div className="card max-w-xl">
      <table className="w-full">
        <tbody>
          {Object.entries(sys).map(([k, v]) => (
            <tr key={k} className="rule">
              <td className="meta uppercase py-1.5 pr-4">{k}</td>
              <td className="text-[13px] py-1.5">{Array.isArray(v) ? v.join(", ") : String(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
