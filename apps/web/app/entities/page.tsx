"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { PageHeader } from "../components/Shell";
import { DocLink, Empty, Loading } from "../components/ui";

const TYPES = ["", "PERSON", "ORGANIZATION", "LOCATION", "COUNTRY", "EVENT", "INSTITUTION", "MILITARY_UNIT"];

export default function Entities() {
  const [type, setType] = useState("");
  const [items, setItems] = useState<any[] | null>(null);
  const [sel, setSel] = useState<any>(null);

  useEffect(() => {
    api.entities({ entity_type: type || undefined, limit: 200 })
      .then((r) => setItems(r.entities))
      .catch(() => setItems([]));
  }, [type]);

  function open(id: number) {
    api.entity(id).then(setSel).catch(() => {});
  }

  return (
    <div>
      <PageHeader eyebrow="Entities" title="Entity Explorer" />
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_400px]">
        <section className="px-10 py-8 rule lg:border-r border-ink-20">
          <div className="flex gap-2 flex-wrap mb-5">
            {TYPES.map((t) => (
              <button key={t} className={type === t ? "chip bg-wine text-white" : "chip cursor-pointer"} onClick={() => setType(t)}>
                {t || "ALL"}
              </button>
            ))}
          </div>
          {!items && <Loading />}
          {items && items.length === 0 && <Empty title="No entities extracted yet." />}
          <div className="flex flex-wrap gap-2">
            {items?.map((e) => (
              <button key={e.id} className="chip cursor-pointer hover:bg-deep" onClick={() => open(e.id)}>
                {e.name} <span className="text-ink-50">· {e.type} · {e.mention_count}</span>
              </button>
            ))}
          </div>
        </section>
        <aside className="px-6 py-8">
          <div className="eyebrow mb-3">Entity Detail</div>
          {!sel && <div className="meta">Select an entity to see linked documents.</div>}
          {sel && (
            <div>
              <div className="text-[22px]">{sel.name}</div>
              <div className="meta mt-1">{sel.type}</div>
              {sel.coordinates ? (
                <div className="meta mt-2">
                  Coordinates: {sel.coordinates.lat}, {sel.coordinates.lon} ({sel.coordinates.precision})
                </div>
              ) : (
                <div className="meta mt-2">No verified coordinates.</div>
              )}
              <div className="eyebrow mt-5 mb-2">Documents</div>
              {sel.documents?.map((d: any, i: number) => (
                <div key={i} className="rule py-2">
                  <DocLink id={d.document_id}>{d.title || d.document_id}</DocLink>
                  <span className="meta"> · p. {d.page ?? "?"}</span>
                </div>
              ))}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
