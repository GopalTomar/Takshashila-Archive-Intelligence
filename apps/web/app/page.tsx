"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "./lib/api";
import { PageHeader } from "./components/Shell";
import { Loading, ErrorNote } from "./components/ui";

const METRICS: [string, string][] = [
  ["documents", "Documents"],
  ["pages", "Pages"],
  ["chunks", "Chunks"],
  ["embeddings", "Embeddings"],
  ["collections", "Collections"],
  ["sources", "Sources"],
  ["authors", "Authors"],
  ["topics", "Topics"],
  ["entities", "Entities"],
  ["ocr_processed", "OCR Processed"],
  ["indexed_documents", "Indexed"],
  ["failed_processing", "Failed Processing"],
  ["ingestion_jobs", "Ingestion Jobs"],
  ["crawl_jobs", "Crawl Jobs"],
];

// Restrained horizontal bar list (wine bars) with an explicit empty state.
function BarList({ title, data }: { title: string; data: { label: string; count: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <div className="card">
      <div className="eyebrow mb-3">{title}</div>
      {(!data || data.length === 0) && <div className="meta">No data available</div>}
      <div className="space-y-1.5">
        {data.map((d) => (
          <div key={d.label} className="grid grid-cols-[120px_1fr_40px] items-center gap-2">
            <span className="meta truncate" title={d.label}>{d.label}</span>
            <span className="h-3 bg-wine" style={{ width: `${Math.max(3, (d.count / max) * 100)}%` }} />
            <span className="meta tabnums text-right">{d.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function healthRow(key: string, v: any): { label: string; value: string; ok: boolean | null } {
  switch (key) {
    case "database":
      return { label: "Database", value: v.ok ? `OK (${v.dialect})` : `error`, ok: v.ok };
    case "pgvector":
      return { label: "pgvector", value: v.available ? `available ${v.version || ""}`.trim() : (v.note || "unavailable"), ok: v.available };
    case "redis":
      return { label: "Redis", value: !v.configured ? "not configured" : v.connected ? "connected" : "disconnected", ok: v.configured ? v.connected : null };
    case "worker":
      return { label: "Worker", value: v.running === null ? (v.note || "in-process") : v.running ? `running (${v.workers})` : "stopped", ok: v.running };
    case "embeddings":
      return { label: "Embeddings", value: v.enabled ? `${v.provider}${v.is_real_semantic ? "" : " (not semantic)"}` : "disabled", ok: v.enabled };
    case "ocr":
      return { label: "OCR", value: v.tesseract_available ? (v.version || "available") : "unavailable", ok: v.tesseract_available };
    case "jobs":
      return { label: "Jobs backend", value: v.backend, ok: true };
    default:
      return { label: key, value: JSON.stringify(v), ok: null };
  }
}

export default function Home() {
  const [stats, setStats] = useState<any>(null);
  const [dist, setDist] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [err, setErr] = useState<string>("");
  const [includeDemo, setIncludeDemo] = useState(false);

  const load = useCallback(() => {
    api.stats(includeDemo).then(setStats).catch((e) => setErr(String(e.message)));
    api.distributions(includeDemo).then(setDist).catch(() => setDist(null));
  }, [includeDemo]);

  useEffect(() => {
    load();
    api.ready().then(setHealth).catch(() => {});
  }, [load]);

  const onlyDemo = stats && !includeDemo && stats.documents === 0;

  return (
    <div>
      <PageHeader
        eyebrow="Takshashila Archive Intelligence"
        title="Research Workstation"
        right={
          <Link href="/ask" className="btn">
            Ask the Archive
          </Link>
        }
      />

      <section className="px-10 py-8 rule">
        <div className="flex items-center justify-between mb-4">
          <div className="eyebrow">Archive Status - live database counts</div>
          <label className="meta flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={includeDemo} onChange={(e) => setIncludeDemo(e.target.checked)} />
            Include demo data
          </label>
        </div>
        {err && <ErrorNote message={`Could not reach API at ${api.base}: ${err}`} />}
        {!stats && !err && <Loading />}
        {stats && (
          <>
            {stats.empty && (
              <div className="border border-ink-20 bg-deep p-6 mb-6">
                <div className="text-[18px] mb-1">No documents indexed yet.</div>
                <div className="meta">
                  Run an ingestion job from{" "}
                  <Link href="/archive" className="underline text-wine">Archive - Ingestion</Link>, or seed demo data in Settings.
                </div>
              </div>
            )}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 border border-ink-20">
              {METRICS.map(([key, label], i) => (
                <div key={key} className="p-4 border-r border-b border-ink-20">
                  <div className="text-[28px] leading-none font-normal tabnums text-wine">{stats[key] ?? 0}</div>
                  <div className="meta mt-1">{label}</div>
                </div>
              ))}
            </div>
            <div className="meta mt-3">
              Semantic search:{" "}
              {stats.semantic_search?.enabled ? (
                <span className="text-positive">enabled ({stats.semantic_search.provider}, dim {stats.semantic_search.dimensions})</span>
              ) : (
                <span className="text-ink-50">
                  not active - {stats.semantic_search?.provider === "none" ? "no embedding provider configured; keyword search only" : `${stats.semantic_search?.provider} embedder is not a real semantic model`}
                </span>
              )}
            </div>
            {onlyDemo && (
              <div className="meta mt-1 text-gold">Only demo/synthetic data is loaded (tick "Include demo data" to view it).</div>
            )}
          </>
        )}
      </section>

      {/* Distributions */}
      <section className="px-10 py-8 rule grid md:grid-cols-2 lg:grid-cols-3 gap-5">
        <BarList title="Documents by Year" data={dist?.documents_by_year || []} />
        <BarList title="Documents by Type" data={dist?.documents_by_type || []} />
        <BarList title="Sources" data={(dist?.sources || []).map((s: any) => ({ label: s.key, count: s.count }))} />
        <BarList title="OCR Status" data={dist?.ocr_status || []} />
        <BarList title="Index Status" data={dist?.index_status || []} />
        <BarList title="Embedding Status" data={dist?.embedding_status || []} />
      </section>

      {/* System health + quick research */}
      <section className="px-10 py-8 grid md:grid-cols-2 gap-6">
        <div className="card">
          <div className="eyebrow mb-3">System Health</div>
          {!health && <Loading />}
          {health && (
            <table className="w-full">
              <tbody>
                {["database", "pgvector", "redis", "worker", "jobs", "embeddings", "ocr"]
                  .filter((k) => health.checks?.[k])
                  .map((k) => {
                    const r = healthRow(k, health.checks[k]);
                    return (
                      <tr key={k} className="rule">
                        <td className="meta uppercase py-1.5">{r.label}</td>
                        <td className="text-[13px] py-1.5 text-right">
                          <span className={r.ok === true ? "text-positive" : r.ok === false ? "text-negative" : ""}>{r.value}</span>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          )}
        </div>
        <div className="card">
          <div className="eyebrow mb-2">Quick Research</div>
          <h3 className="text-[22px] mb-2">Ask a grounded question</h3>
          <p className="text-ink-70 text-[14px] mb-4">
            The assistant answers only from retrieved archive evidence, with clickable
            citations that resolve to the exact document and page. If the archive lacks
            evidence, it says so rather than guessing.
          </p>
          <Link href="/ask" className="btn-ghost">Open Ask the Archive</Link>
        </div>
      </section>

      <section className="px-10 py-6">
        <div className="meta">
          Methodology: AI outputs are research assistance, not authoritative historical
          sources. Original documents remain the primary source.{" "}
          <Link href="/methodology" className="underline text-wine">Read the methodology</Link>
        </div>
      </section>
    </div>
  );
}
