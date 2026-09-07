"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "../lib/api";
import { PageHeader } from "../components/Shell";
import { ErrorNote, Loading } from "../components/ui";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [includeDemo, setIncludeDemo] = useState(true);
  const [res, setRes] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function run() {
    if (!q.trim()) return;
    setLoading(true);
    setErr("");
    try {
      const r = await api.search({ query: q, mode, top_k: 20, filters: { include_demo: includeDemo } });
      setRes(r);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Search" title="Archive Search" />
      <section className="px-10 py-8 rule">
        <div className="flex gap-3">
          <input
            className="field flex-1"
            placeholder="Search the archive…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
          />
          <select className="field w-40" value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="hybrid">Hybrid</option>
            <option value="keyword">Keyword</option>
            <option value="semantic">Semantic</option>
          </select>
          <button className="btn" onClick={run} disabled={loading}>
            Search
          </button>
        </div>
        <label className="meta flex items-center gap-2 mt-3 cursor-pointer">
          <input type="checkbox" checked={includeDemo} onChange={(e) => setIncludeDemo(e.target.checked)} />
          Include demo data
        </label>
      </section>

      <section className="px-10 py-8">
        {err && <ErrorNote message={err} />}
        {loading && <Loading />}
        {res && (
          <>
            <div className="meta mb-4">
              {res.count} results · requested {res.requested_mode} · effective{" "}
              <span className="text-wine">{res.effective_mode}</span>
              {res.note && <span className="text-negative"> · {res.note}</span>}
            </div>
            {res.count === 0 && (
              <div className="border border-ink-20 bg-deep p-6">
                <div className="text-[16px] mb-1">No results.</div>
                <div className="meta">Try broader terms, remove filters, or widen the date range.</div>
              </div>
            )}
            <div className="space-y-3">
              {res.results.map((r: any, i: number) => (
                <div key={i} className="card">
                  <div className="flex items-center justify-between">
                    <div className="meta">
                      {r.document_id} {r.date ? `· ${r.date}` : ""} {r.document_type ? `· ${r.document_type}` : ""}
                      {r.page != null ? ` · p. ${r.page}` : ""}
                    </div>
                    <div className="meta">score {r.combined_score}</div>
                  </div>
                  <div className="text-[18px] mt-1">
                    {r.document_id ? (
                      <Link href={`/documents/${r.document_id}?page=${r.page || 1}`} className="text-wine underline underline-offset-2">
                        {r.title || "Untitled"}
                      </Link>
                    ) : (
                      r.title || "Untitled"
                    )}
                  </div>
                  {r.author && <div className="meta mt-1">{r.author}</div>}
                  <div className="text-[14px] text-ink-70 mt-2">{r.matched_passage}</div>
                  <div className="meta mt-2">Matched: {r.match_reasons?.join(" · ")}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
