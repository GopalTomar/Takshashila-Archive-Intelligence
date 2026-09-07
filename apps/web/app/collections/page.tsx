"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { PageHeader } from "../components/Shell";
import { Empty, Loading } from "../components/ui";

export default function Collections() {
  const [cols, setCols] = useState<any[] | null>(null);
  const [topics, setTopics] = useState<any[]>([]);
  useEffect(() => {
    api.collections().then((r) => setCols(r.collections)).catch(() => setCols([]));
    api.topics().then((r) => setTopics(r.topics)).catch(() => {});
  }, []);
  return (
    <div>
      <PageHeader eyebrow="Collections" title="Collections & Topics" />
      <section className="px-10 py-8 rule">
        <div className="eyebrow mb-4">Collections</div>
        {!cols && <Loading />}
        {cols && cols.length === 0 && <Empty title="No collections yet." />}
        <div className="grid md:grid-cols-3 gap-5">
          {cols?.map((c) => (
            <div key={c.collection_key} className="card">
              <div className="meta">{c.collection_key}</div>
              <div className="text-[20px] mt-1">{c.name}</div>
              <div className="text-[13px] text-ink-70 mt-2">{c.description}</div>
              <div className="meta mt-3">{c.document_count} documents</div>
            </div>
          ))}
        </div>
      </section>
      <section className="px-10 py-8">
        <div className="eyebrow mb-4">Topics</div>
        <div className="flex flex-wrap gap-2">
          {topics.map((t) => (
            <span key={t.key} className="chip">
              {t.label} <span className="text-ink-50">· {t.document_count}</span>
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
