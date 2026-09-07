"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { PageHeader } from "../components/Shell";
import { DemoTag, ErrorNote, Loading, StatusChip } from "../components/ui";

export default function ArchivePage() {
  const [tab, setTab] = useState<"browse" | "ingestion">("browse");
  return (
    <div>
      <PageHeader
        eyebrow="Archive"
        title="Archive & Ingestion"
        right={
          <div className="flex gap-2">
            <button className={tab === "browse" ? "btn" : "btn-ghost"} onClick={() => setTab("browse")}>
              Browse
            </button>
            <button className={tab === "ingestion" ? "btn" : "btn-ghost"} onClick={() => setTab("ingestion")}>
              Ingestion
            </button>
          </div>
        }
      />
      {tab === "browse" ? <Browse /> : <Ingestion />}
    </div>
  );
}

function Browse() {
  const [data, setData] = useState<any>(null);
  const [includeDemo, setIncludeDemo] = useState(true);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.documents({ include_demo: includeDemo, limit: 50 }).then(setData).catch((e) => setErr(e.message));
  }, [includeDemo]);
  return (
    <section className="px-10 py-8">
      <label className="meta flex items-center gap-2 mb-4 cursor-pointer">
        <input type="checkbox" checked={includeDemo} onChange={(e) => setIncludeDemo(e.target.checked)} />
        Include demo data
      </label>
      {err && <ErrorNote message={err} />}
      {!data && !err && <Loading />}
      {data && data.total === 0 && (
        <div className="border border-ink-20 bg-deep p-6">
          <div className="text-[16px] mb-1">No archival documents have been indexed yet.</div>
          <div className="meta">Run an ingestion job from the Ingestion tab, or seed demo data in Settings.</div>
        </div>
      )}
      {data && data.total > 0 && (
        <table className="w-full">
          <thead>
            <tr>
              {["ID", "Title", "Date", "Type", "OCR", "Index"].map((h) => (
                <th key={h} className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-ink-50 text-left border-b border-ink-20 py-2">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.items.map((d: any) => (
              <tr key={d.document_id} className="border-b border-ink-20 hover:bg-deep">
                <td className="py-2 pr-3 font-mono text-[12px]">{d.document_id}</td>
                <td className="py-2 pr-3 text-[14px]">
                  <Link href={`/documents/${d.document_id}`} className="text-wine underline underline-offset-2">
                    {d.title || "Untitled"}
                  </Link>{" "}
                  {d.is_demo && <DemoTag />}
                </td>
                <td className="py-2 pr-3 text-[13px] tabnums">{d.date || "—"}</td>
                <td className="py-2 pr-3 text-[13px]">{d.document_type || "—"}</td>
                <td className="py-2 pr-3"><StatusChip status={d.ocr_status} /></td>
                <td className="py-2 pr-3"><StatusChip status={d.index_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Ingestion() {
  const [sources, setSources] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [crawls, setCrawls] = useState<any[]>([]);
  const [sel, setSel] = useState("");
  const [seeds, setSeeds] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  function refresh() {
    api.jobs().then((r) => setJobs(r.jobs)).catch(() => {});
    api.crawls().then((r) => setCrawls(r.crawls)).catch(() => {});
  }
  useEffect(() => {
    api.sources().then((r) => {
      setSources(r.sources);
      setSel(r.sources[0]?.id || "");
    }).catch((e) => setErr(e.message));
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, []);

  async function startCrawl() {
    setErr("");
    setMsg("");
    try {
      const seedList = seeds.split("\n").map((s) => s.trim()).filter(Boolean);
      const r = await api.startCrawl({
        source_key: sel,
        seed_urls: seedList.length ? seedList : undefined,
        confirm: sel !== "fixtures",
      });
      setMsg(`Crawl job #${r.job_id} started (${r.status}).`);
      refresh();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <section className="px-10 py-8 grid lg:grid-cols-2 gap-8">
      <div>
        <div className="eyebrow mb-3">New Crawl</div>
        <div className="card">
          <label className="meta block mb-1">Source</label>
          <select className="field mb-3" value={sel} onChange={(e) => setSel(e.target.value)}>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.seed_url_count} seed URLs)
              </option>
            ))}
          </select>
          <label className="meta block mb-1">Seed URLs (one per line — verified public URLs only)</label>
          <textarea
            className="field min-h-[90px] font-mono text-[12px]"
            placeholder="https://…"
            value={seeds}
            onChange={(e) => setSeeds(e.target.value)}
          />
          <div className="meta my-2">
            Live crawls require explicit confirmation and respect robots.txt, an allowlist, and rate limits.
            Nothing is fabricated — the crawl report shows exactly what was found.
          </div>
          <button className="btn" onClick={startCrawl}>Start Crawl</button>
          {msg && <div className="meta mt-2 text-positive">{msg}</div>}
          {err && <div className="mt-2"><ErrorNote message={err} /></div>}
        </div>

        <div className="eyebrow mt-8 mb-3">Recent Crawls</div>
        {crawls.length === 0 && <div className="meta">No crawls yet.</div>}
        {crawls.map((c) => (
          <div key={c.id} className="border border-ink-20 p-3 mb-2">
            <div className="flex justify-between">
              <span className="font-mono text-[12px]">#{c.id} · {c.source_key}</span>
              <StatusChip status={c.status} />
            </div>
            {c.stats && (
              <div className="meta mt-1">
                discovered {c.stats.urls_discovered} · downloaded {c.stats.urls_downloaded} · failed{" "}
                {c.stats.urls_failed} · blocked {c.stats.urls_blocked} · duplicates {c.stats.duplicates}
              </div>
            )}
          </div>
        ))}
      </div>

      <div>
        <div className="eyebrow mb-3">Jobs</div>
        {jobs.length === 0 && <div className="meta">No jobs yet.</div>}
        {jobs.map((j) => (
          <div key={j.id} className="border border-ink-20 p-3 mb-2">
            <div className="flex justify-between items-center">
              <span className="font-mono text-[12px]">#{j.id} · {j.job_type}</span>
              <div className="flex items-center gap-2">
                <StatusChip status={j.status} />
                {j.status === "failed" && (
                  <button className="chip cursor-pointer" onClick={() => api.retryJob(j.id).then(() => {})}>
                    retry
                  </button>
                )}
              </div>
            </div>
            {j.error_type && <div className="meta mt-1 text-negative">{j.error_type}</div>}
          </div>
        ))}
      </div>
    </section>
  );
}
