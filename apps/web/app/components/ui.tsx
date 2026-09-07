"use client";
import Link from "next/link";

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="border border-ink-20 bg-deep p-10 text-center">
      <div className="text-[18px] mb-2">{title}</div>
      {hint && <div className="meta">{hint}</div>}
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <div className="meta py-8">{label}</div>;
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="border-l-2 border-negative pl-4 py-2 text-[14px] text-negative bg-paper">
      {message}
    </div>
  );
}

export function Confidence({ value }: { value: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    supported: { label: "SUPPORTED", cls: "text-positive border-positive" },
    partially_supported: { label: "PARTIALLY SUPPORTED", cls: "text-gold border-gold" },
    insufficient_evidence: { label: "INSUFFICIENT EVIDENCE", cls: "text-negative border-negative" },
  };
  const m = map[value] || { label: value?.toUpperCase() || "UNKNOWN", cls: "text-ink-50 border-ink-20" };
  return <span className={`chip ${m.cls}`}>{m.label}</span>;
}

export function StatusChip({ status }: { status: string }) {
  const good = ["succeeded", "ok"].includes(status);
  const bad = ["failed", "error"].includes(status);
  const cls = good ? "text-positive border-positive" : bad ? "text-negative border-negative" : "text-ink-50 border-ink-20";
  return <span className={`chip ${cls}`}>{status}</span>;
}

export function DemoTag() {
  return <span className="chip bg-gold text-ink border-ink-20">DEMO — NOT ARCHIVAL</span>;
}

export function DocLink({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <Link href={`/documents/${id}`} className="text-wine underline underline-offset-2">
      {children}
    </Link>
  );
}
