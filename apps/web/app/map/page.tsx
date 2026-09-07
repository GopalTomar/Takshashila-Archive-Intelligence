"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { PageHeader } from "../components/Shell";
import { Empty, Loading } from "../components/ui";

// Document-linked geographic explorer. Coordinates are NEVER invented — only
// entities with supplied/verified coordinates appear. First version renders a
// simple equirectangular plot; a full GIS layer is a documented extension.
export default function MapPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    api.mapEntities().then(setData).catch(() => setData({ points: [] }));
  }, []);

  const project = (lat: number, lon: number) => ({
    left: ((lon + 180) / 360) * 100,
    top: ((90 - lat) / 180) * 100,
  });

  return (
    <div>
      <PageHeader eyebrow="Map" title="Geographic Explorer" />
      <section className="px-10 py-8">
        <div className="meta mb-4">{data?.note}</div>
        {!data && <Loading />}
        {data && data.points.length === 0 && (
          <Empty
            title="No geolocated entities."
            hint="Coordinates are added only when supplied by a source or verified — never fabricated."
          />
        )}
        {data && data.points.length > 0 && (
          <div className="relative border border-ink-20 bg-deep" style={{ aspectRatio: "2 / 1" }}>
            {data.points.map((p: any) => {
              const pos = project(p.lat, p.lon);
              return (
                <div
                  key={p.id}
                  title={`${p.name} (${p.precision})`}
                  className="absolute w-2 h-2 bg-wine"
                  style={{ left: `${pos.left}%`, top: `${pos.top}%` }}
                />
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
