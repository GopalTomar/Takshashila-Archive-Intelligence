"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { PageHeader } from "../components/Shell";
import { Confidence, Empty, Loading } from "../components/ui";

export default function Notes() {
  const [sessions, setSessions] = useState<any[] | null>(null);
  const [notes, setNotes] = useState<any[]>([]);
  const [body, setBody] = useState("");
  const [detail, setDetail] = useState<any>(null);

  function refresh() {
    api.sessions().then((r) => setSessions(r.sessions)).catch(() => setSessions([]));
    api.notes().then((r) => setNotes(r.notes)).catch(() => {});
  }
  useEffect(refresh, []);

  async function addNote() {
    if (!body.trim()) return;
    await api.createNote({ body });
    setBody("");
    refresh();
  }

  return (
    <div>
      <PageHeader eyebrow="Research Notes" title="Saved Research" />
      <div className="grid lg:grid-cols-2">
        <section className="px-10 py-8 rule lg:border-r border-ink-20">
          <div className="eyebrow mb-3">Research Sessions</div>
          {!sessions && <Loading />}
          {sessions && sessions.length === 0 && <Empty title="No saved sessions yet." hint="Use Ask & Save Session." />}
          {sessions?.map((s) => (
            <div key={s.id} className="border border-ink-20 p-3 mb-2 hover:bg-deep cursor-pointer" onClick={() => api.session(s.id).then(setDetail)}>
              <div className="flex justify-between">
                <span className="text-[15px]">{s.title || s.question}</span>
                {s.confidence && <Confidence value={s.confidence} />}
              </div>
              <div className="meta mt-1">
                {s.model_id} · {s.retrieval_mode} · {new Date(s.created_at).toLocaleString()}
              </div>
            </div>
          ))}

          <div className="eyebrow mt-8 mb-3">Notes</div>
          <textarea className="field min-h-[80px]" placeholder="Write a research note…" value={body} onChange={(e) => setBody(e.target.value)} />
          <button className="btn mt-2" onClick={addNote}>Save Note</button>
          <div className="mt-4 space-y-2">
            {notes.map((n) => (
              <div key={n.id} className="rule py-2 text-[14px]">{n.body}</div>
            ))}
          </div>
        </section>

        <aside className="px-6 py-8">
          <div className="eyebrow mb-3">Session Detail</div>
          {!detail && <div className="meta">Select a session to view its answer, sources and citations.</div>}
          {detail && (
            <div>
              <div className="text-[18px] mb-2">{detail.question}</div>
              <div className="prose-answer whitespace-pre-wrap text-[14px]">{detail.answer}</div>
              {detail.sources?.length > 0 && (
                <>
                  <div className="eyebrow mt-5 mb-2">Sources</div>
                  {detail.sources.map((s: any) => (
                    <div key={s.chunk_id} className="rule py-2 meta">
                      [{s.ref}] {s.document_id} · p. {s.page}
                    </div>
                  ))}
                </>
              )}
              <div className="meta mt-3">No API keys are ever stored in a research session.</div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
