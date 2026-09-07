"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { PageHeader } from "../components/Shell";
import { Empty, Loading } from "../components/ui";

export default function Timeline() {
  const [events, setEvents] = useState<any[] | null>(null);
  useEffect(() => {
    api.timeline().then((r) => setEvents(r.events)).catch(() => setEvents([]));
  }, []);
  return (
    <div>
      <PageHeader eyebrow="Timeline" title="Historical Timeline" />
      <section className="px-10 py-8">
        <div className="meta mb-6">
          Events are evidence-backed. Model-extracted events are labelled AI-extracted until a human verifies them.
        </div>
        {!events && <Loading />}
        {events && events.length === 0 && (
          <Empty
            title="No timeline events yet."
            hint="Events are created from verified evidence or reviewed AI extraction — never fabricated."
          />
        )}
        <div className="border-l-2 border-wine pl-6 space-y-6">
          {events?.map((e) => (
            <div key={e.event_key} className="relative">
              <div className="meta tabnums">{e.date || "date unknown"} · {e.date_precision}</div>
              <div className="text-[20px] mt-1">{e.title}</div>
              <div className="text-[14px] text-ink-70 mt-1">{e.description}</div>
              <div className="mt-2 flex items-center gap-3">
                <span className={`chip ${e.verified ? "text-positive border-positive" : "text-gold border-gold"}`}>
                  {e.label}
                </span>
                <span className="meta">{e.document_count} linked documents</span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
