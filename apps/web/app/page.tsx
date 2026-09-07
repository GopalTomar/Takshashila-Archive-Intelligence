"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "./lib/api";
import { PageHeader } from "./components/Shell";
import { Loading, ErrorNote } from "./components/ui";

const METRICS: [string, string][] = [
  ["documents", "Documents"],
  ["pages", "Pages"],
  ["collections", "Collections"],
  ["sources", "Sources"],
  ["authors", "Authors"],
  ["topics", "Topics"],
  ["entities", "Entities"],
  ["ocr_processed", "OCR Processed"],
  ["indexed_documents", "Indexed"],
  ["failed_processing", "Failed Processing"],
];

export default function Home() {
  const [stats, setStats] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    api.stats().then(setStats).catch((e) => setErr(String(e.message)));
    api.ready().then(setHealth).catch(() => {});
  }, []);

  return (
    <div>
      <PageHeader
        eyebrow="Takshashila Archive Intelligence"
        title="Research Workstation"
        right={
          <Link href="/ask" className="btn">
            Ask the Archive →
          </Link>
        }
      />

      <section className="px-10 py-8 rule">
        <div className="eyebrow mb-4">Archive Status — live database counts</div>
        {err && <ErrorNote message={`Could not reach API at ${api.base}: ${err}`} />}
        {!stats && !err && <Loading />}
        {stats && (
          <>
            {stats.empty && (
              <div className="border border-ink-20 bg-deep p-6 mb-6">
                <div className="text-[18px] mb-1">No documents indexed yet.</div>
                <div className="meta">
                  Run an ingestion job from{" "}
                  <Link href="/archive" className="underline text-wine">
                    Archive → Ingestion
                  </Link>
                  , or seed demo data in Settings.
                </div>
              </div>
            )}
            <div className="grid grid-cols-2 md:grid-cols-5 border border-ink-20">
              {METRICS.map(([key, label], i) => (
                <div
                  key={key}
                  className="p-5 border-ink-20"
                  style={{
                    borderRight: (i + 1) % 5 === 0 ? "none" : "1px solid var(--ink-20)",
                    borderBottom: i < 5 ? "1px solid var(--ink-20)" : "none",
                  }}
                >
                  <div className="kpi text-wine">{stats[key] ?? 0}</div>
                  <div className="meta mt-1">{label}</div>
                </div>
              ))}
            </div>
            <div className="meta mt-3">
              Semantic search:{" "}
              {stats.semantic_search?.enabled ? (
                <span className="text-positive">enabled ({stats.semantic_search.provider})</span>
              ) : (
                <span className="text-ink-50">not configured — keyword search only</span>
              )}
            </div>
          </>
        )}
      </section>

      <section className="px-10 py-8 rule grid md:grid-cols-2 gap-6">
        <div className="card">
          <div className="eyebrow mb-2">Quick Research</div>
          <h3 className="text-[22px] mb-2">Ask a grounded question</h3>
          <p className="text-ink-70 text-[14px] mb-4">
            The assistant answers only from retrieved archive evidence, with clickable
            citations that resolve to the exact document and page. If the archive lacks
            evidence, it says so rather than guessing.
          </p>
          <Link href="/ask" className="btn-ghost">
            Open Ask the Archive →
          </Link>
        </div>
        <div className="card">
          <div className="eyebrow mb-2">System Health</div>
          <h3 className="text-[22px] mb-3">Services</h3>
          {!health && <Loading />}
          {health && (
            <table className="w-full">
              <tbody>
                {Object.entries(health.checks || {}).map(([k, v]: any) => (
                  <tr key={k} className="rule">
                    <td className="meta uppercase py-1.5">{k}</td>
                    <td className="text-[13px] py-1.5 text-right">
                      {v.ok || v.available || v.enabled
                        ? "ok"
                        : v.tesseract_available
                        ? "ok"
                        : v.detail || v.note || v.backend || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section className="px-10 py-6">
        <div className="meta">
          Methodology: AI outputs are research assistance, not authoritative historical
          sources. Original documents remain the primary source. Verify citations against
          the underlying document.{" "}
          <Link href="/methodology" className="underline text-wine">
            Read the methodology →
          </Link>
        </div>
      </section>
    </div>
  );
}
