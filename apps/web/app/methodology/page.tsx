import { PageHeader } from "../components/Shell";

export default function Methodology() {
  return (
    <div>
      <PageHeader eyebrow="Research Integrity" title="Methodology" />
      <section className="px-10 py-8 max-w-3xl space-y-5 text-[15px] leading-[1.7] text-ink-70">
        <p>
          Takshashila Archive Intelligence is a provenance-first research tool. Its purpose is to
          preserve, catalogue and make searchable publicly accessible archival material, and to
          assist research over that material with grounded, cited AI.
        </p>
        <div className="border-l-2 border-wine pl-5">
          <p className="text-ink">
            AI-generated outputs are research assistance, not authoritative historical sources.
          </p>
          <p className="text-ink">Original documents remain the primary source.</p>
          <p className="text-ink">Citations should always be checked against the underlying document.</p>
        </div>
        <h3 className="text-[22px] text-ink font-medium pt-2">What the AI does</h3>
        <p>
          The assistant retrieves evidence from the indexed archive and answers only from that
          evidence (in Archive Only mode). Every substantive claim carries a citation that resolves
          to an exact document and page. Citations are validated against the database; the confidence
          label (Supported / Partially supported / Insufficient evidence) is derived from that
          validation, not from the model's own assertion.
        </p>
        <h3 className="text-[22px] text-ink font-medium pt-2">What the AI does not do</h3>
        <p>
          It does not invent documents, quotations, dates, page numbers or citations. If the archive
          lacks sufficient evidence, it says so rather than answering from general knowledge. AI-derived
          metadata and AI-extracted timeline events are labelled as such and require human review before
          they are treated as verified.
        </p>
        <h3 className="text-[22px] text-ink font-medium pt-2">Provenance</h3>
        <p>
          Every document records its source URL, any archived (Wayback) copy, local path, SHA-256
          checksum and retrieval date. Originals are never overwritten; OCR and text derivatives are
          stored separately.
        </p>
        <h3 className="text-[22px] text-ink font-medium pt-2">Rights</h3>
        <p>
          Public accessibility does not imply a right to redistribute. Records can be stored
          metadata-only where redistribution of the file is inappropriate; rights and access status are
          tracked per document.
        </p>
      </section>
    </div>
  );
}
