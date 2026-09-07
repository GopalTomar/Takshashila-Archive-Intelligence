"use client";
import { Suspense, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { api } from "../../lib/api";
import { PageHeader } from "../../components/Shell";
import { DemoTag, ErrorNote, Loading, StatusChip } from "../../components/ui";
import { useModel } from "../../components/ModelContext";

export default function DocumentViewerPage() {
  return (
    <Suspense fallback={<div className="p-10"><Loading /></div>}>
      <DocumentViewer />
    </Suspense>
  );
}

function DocumentViewer() {
  const params = useParams();
  const search = useSearchParams();
  const id = params.id as string;
  const initialPage = parseInt(search.get("page") || "1", 10);

  const { settings } = useModel();
  const [doc, setDoc] = useState<any>(null);
  const [pages, setPages] = useState<any[]>([]);
  const [page, setPage] = useState(initialPage);
  const [err, setErr] = useState("");
  const [within, setWithin] = useState("");
  const [ask, setAsk] = useState("");
  const [askResp, setAskResp] = useState<any>(null);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    api.document(id).then(setDoc).catch((e) => setErr(e.message));
    api.documentPages(id).then((r) => setPages(r.pages)).catch(() => {});
  }, [id]);

  const current = pages.find((p) => p.page_number === page);
  const highlight = (text: string) => {
    if (!within.trim() || !text) return text;
    const parts = text.split(new RegExp(`(${within.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "ig"));
    return parts.map((p, i) =>
      p.toLowerCase() === within.toLowerCase() ? (
        <mark key={i} className="bg-gold-soft">{p}</mark>
      ) : (
        <span key={i}>{p}</span>
      )
    );
  };

  async function askDoc(summarize = false) {
    setAsking(true);
    setAskResp(null);
    try {
      const body = {
        question: summarize ? "Summarize this document with page citations." : ask,
        provider_id: settings.provider_id,
        model_id: settings.model_id,
        archive_only: true,
        reasoning: settings.reasoning,
        temperature: settings.temperature,
        filters: { include_demo: doc?.is_demo || false },
      };
      const r = summarize ? await api.summarizeDocument(id, body) : await api.askDocument(id, body);
      setAskResp(r);
    } catch (e: any) {
      setAskResp({ answer: e.message, confidence: "insufficient_evidence" });
    } finally {
      setAsking(false);
    }
  }

  if (err) return <div className="p-10"><ErrorNote message={err} /></div>;
  if (!doc) return <div className="p-10"><Loading /></div>;

  return (
    <div>
      <PageHeader
        eyebrow={doc.document_id}
        title={doc.title || "Untitled document"}
        right={doc.is_demo ? <DemoTag /> : undefined}
      />
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px]">
        {/* Viewer */}
        <div className="px-10 py-6 rule lg:border-r border-ink-20 min-w-0">
          <div className="flex items-center gap-3 mb-4">
            <button className="btn-ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              ← Prev
            </button>
            <span className="meta">
              Page {page} {doc.page_count ? `of ${doc.page_count}` : ""}
            </span>
            <button
              className="btn-ghost"
              disabled={doc.page_count ? page >= doc.page_count : false}
              onClick={() => setPage(page + 1)}
            >
              Next →
            </button>
            <input
              className="field flex-1"
              placeholder="Search within document…"
              value={within}
              onChange={(e) => setWithin(e.target.value)}
            />
            {!doc.metadata_only && (
              <a className="btn-ghost" href={api.fileUrl(id)} target="_blank" rel="noreferrer">
                Open Original
              </a>
            )}
          </div>

          <div className="border border-ink-20 p-6 min-h-[400px] bg-paper">
            {current ? (
              <div className="whitespace-pre-wrap text-[14px] leading-[1.7]">
                {highlight(current.text || "")}
                {!current.text && <span className="meta">No extracted text for this page.</span>}
              </div>
            ) : (
              <div className="meta">No page text available.</div>
            )}
          </div>
          {current?.text_source && (
            <div className="meta mt-2">
              Text source: {current.text_source}
              {current.ocr_confidence != null ? ` · OCR confidence ${Math.round(current.ocr_confidence)}%` : ""}
            </div>
          )}

          {/* Ask about this document */}
          <div className="mt-8 border border-ink-20 bg-deep p-4">
            <div className="eyebrow mb-2">Ask about this document</div>
            <div className="flex gap-2">
              <input
                className="field flex-1"
                placeholder="Question scoped to this document…"
                value={ask}
                onChange={(e) => setAsk(e.target.value)}
              />
              <button className="btn" onClick={() => askDoc(false)} disabled={asking || !ask.trim()}>
                Ask
              </button>
              <button className="btn-ghost" onClick={() => askDoc(true)} disabled={asking}>
                Summarize
              </button>
            </div>
            {asking && <Loading label="Retrieving from this document…" />}
            {askResp && (
              <div className="mt-3">
                <div className="prose-answer whitespace-pre-wrap text-[14px]">{askResp.answer}</div>
                {askResp.sources?.length > 0 && (
                  <div className="meta mt-2">
                    Cited pages:{" "}
                    {[...new Set(askResp.sources.map((s: any) => s.page))].join(", ")}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Metadata sidebar */}
        <aside className="px-6 py-6">
          <div className="eyebrow mb-3">Provenance & Metadata</div>
          <table className="w-full">
            <tbody>
              {[
                ["Document ID", doc.document_id],
                ["Author", doc.author || "unknown"],
                ["Date", doc.date || "unknown"],
                ["Type", doc.document_type || "unknown"],
                ["Language", doc.language || "unknown"],
                ["Pages", doc.page_count ?? "unknown"],
                ["Rights", doc.rights_status || "unknown"],
                ["Access", doc.access_status || "unknown"],
                ["Metadata source", doc.metadata_source],
                ["Review", doc.review_status],
                ["SHA-256", doc.sha256 ? doc.sha256.slice(0, 16) + "…" : "unknown"],
              ].map(([k, v]) => (
                <tr key={k as string} className="rule">
                  <td className="meta uppercase py-1.5 pr-3 align-top">{k}</td>
                  <td className="text-[13px] py-1.5 break-words">{v as any}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="eyebrow mt-6 mb-2">Source</div>
          {doc.source_url ? (
            <a className="text-[13px] text-wine underline break-all" href={doc.source_url} target="_blank" rel="noreferrer">
              {doc.source_url} ↗
            </a>
          ) : (
            <div className="meta">unknown</div>
          )}
          {doc.archived_url && (
            <div className="mt-1">
              <span className="meta">Archived copy: </span>
              <a className="text-[13px] text-wine underline break-all" href={doc.archived_url} target="_blank" rel="noreferrer">
                {doc.archived_url} ↗
              </a>
            </div>
          )}

          {doc.topics?.length > 0 && (
            <>
              <div className="eyebrow mt-6 mb-2">Topics</div>
              <div className="flex flex-wrap gap-1.5">
                {doc.topics.map((t: any) => (
                  <span key={t.key} className="chip">{t.label}</span>
                ))}
              </div>
            </>
          )}

          {doc.entities?.length > 0 && (
            <>
              <div className="eyebrow mt-6 mb-2">Entities</div>
              <div className="flex flex-wrap gap-1.5">
                {doc.entities.map((e: any, i: number) => (
                  <span key={i} className="chip">
                    {e.name} <span className="text-ink-50">· {e.type}</span>
                  </span>
                ))}
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
