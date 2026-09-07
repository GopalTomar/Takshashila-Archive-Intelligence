"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "../lib/api";
import { PageHeader } from "../components/Shell";
import { ModelSelector } from "../components/ModelSelector";
import { useModel } from "../components/ModelContext";
import { Confidence, ErrorNote, Loading } from "../components/ui";

export default function AskPage() {
  const { settings } = useModel();
  const [question, setQuestion] = useState("");
  const [includeDemo, setIncludeDemo] = useState(true);
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<any>(null);
  const [err, setErr] = useState("");
  const [saved, setSaved] = useState<number | null>(null);

  async function submit(save = false) {
    if (!question.trim()) return;
    setLoading(true);
    setErr("");
    setSaved(null);
    try {
      const r = await api.ask({
        question,
        provider_id: settings.provider_id,
        model_id: settings.model_id,
        archive_only: settings.archive_only,
        reasoning: settings.reasoning,
        temperature: settings.temperature,
        mode: "hybrid",
        top_k: 8,
        save_session: save,
        filters: { include_demo: includeDemo },
      });
      setResp(r);
      if (r.saved_session_id) setSaved(r.saved_session_id);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Ask the Archive" title="Grounded Research Assistant" />
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px]">
        {/* Center: conversation */}
        <div className="px-10 py-8 rule lg:border-r border-ink-20 min-w-0">
          <div className="mb-4">
            <ModelSelector />
          </div>

          <label className="meta flex items-center gap-2 mb-3 cursor-pointer">
            <input
              type="checkbox"
              checked={includeDemo}
              onChange={(e) => setIncludeDemo(e.target.checked)}
            />
            Include demo data (synthetic — for demonstration only)
          </label>

          <textarea
            className="field min-h-[100px] font-sans"
            placeholder="Ask a research question, e.g. What did the sources say about Aksai Chin between 1954 and 1962?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <div className="flex gap-3 mt-3">
            <button className="btn" onClick={() => submit(false)} disabled={loading}>
              {loading ? "Retrieving…" : "Ask"}
            </button>
            <button className="btn-ghost" onClick={() => submit(true)} disabled={loading}>
              Ask & Save Session
            </button>
          </div>

          {err && <div className="mt-4"><ErrorNote message={err} /></div>}
          {loading && <Loading label="Retrieving evidence and generating a grounded answer…" />}

          {resp && (
            <div className="mt-8">
              <div className="flex items-center gap-3 mb-3">
                <Confidence value={resp.confidence} />
                {saved && <span className="meta">Saved as session #{saved}</span>}
              </div>

              {resp.warnings?.length > 0 && (
                <div className="border-l-2 border-gold pl-4 py-2 mb-4 text-[13px]">
                  {resp.warnings.map((w: string, i: number) => (
                    <div key={i} className="text-ink-70">
                      ⚠ {w}
                    </div>
                  ))}
                </div>
              )}

              <div className="eyebrow mb-2">Answer</div>
              <div className="prose-answer whitespace-pre-wrap">{resp.answer}</div>

              {resp.claims?.length > 0 && (
                <div className="mt-6">
                  <div className="eyebrow mb-2">Claims & Citations</div>
                  {resp.claims.map((c: any, i: number) => (
                    <div key={i} className="rule py-2 text-[14px]">
                      {c.text}{" "}
                      {(c.citation_ids || []).map((id: string) => (
                        <span key={id} className="cite ml-1">
                          {id}
                        </span>
                      ))}
                    </div>
                  ))}
                </div>
              )}

              {/* Transparency */}
              <div className="mt-8 border border-ink-20 bg-deep p-4">
                <div className="eyebrow mb-2">How this answer was produced</div>
                <table className="w-full">
                  <tbody>
                    {[
                      ["Provider", resp.transparency?.provider],
                      ["Model", resp.transparency?.model],
                      ["Reasoning", resp.transparency?.reasoning || "—"],
                      ["Retrieval", resp.transparency?.retrieval_mode],
                      [
                        "Sources",
                        `${resp.documents_retrieved} documents / ${resp.chunks_retrieved} chunks`,
                      ],
                      [
                        "Tokens",
                        resp.transparency?.input_tokens != null
                          ? `${resp.transparency.input_tokens} in / ${resp.transparency.output_tokens} out`
                          : "unavailable",
                      ],
                      ["Cost", resp.transparency?.cost_note],
                    ].map(([k, v]) => (
                      <tr key={k as string}>
                        <td className="meta uppercase py-1 pr-4">{k}</td>
                        <td className="text-[13px] py-1">{v as string}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Right: sources / citations */}
        <aside className="px-6 py-8 bg-paper">
          <div className="eyebrow mb-3">Sources</div>
          {!resp && <div className="meta">Ask a question to see retrieved sources here.</div>}
          {resp?.sources?.length === 0 && (
            <div className="meta">No archival evidence retrieved.</div>
          )}
          {resp?.sources?.map((s: any) => {
            const cv = (resp.citations || []).find((c: any) => c.chunk_id === s.chunk_id);
            const valid = cv ? cv.valid : null;
            return (
              <div key={s.chunk_id} className="border border-ink-20 p-3 mb-3">
                <div className="flex items-center justify-between">
                  <span className="cite">{s.ref}</span>
                  {valid === true && <span className="chip text-positive border-positive">verified</span>}
                  {valid === false && <span className="chip text-negative border-negative">unverified</span>}
                </div>
                <div className="text-[14px] mt-2 font-medium">{s.title || "Untitled"}</div>
                <div className="meta mt-1">
                  {s.document_id}
                  {s.page != null ? ` · p. ${s.page}` : ""}
                  {s.date ? ` · ${s.date}` : ""}
                </div>
                <div className="text-[13px] text-ink-70 mt-2 line-clamp-4">{s.passage}</div>
                <div className="meta mt-2">
                  {s.match_reasons?.join(" · ")}
                </div>
                {s.document_id && (
                  <Link
                    href={`/documents/${s.document_id}?page=${s.page || 1}`}
                    className="meta underline text-wine mt-2 inline-block"
                  >
                    Open document → p. {s.page || 1}
                  </Link>
                )}
              </div>
            );
          })}
        </aside>
      </div>
    </div>
  );
}
