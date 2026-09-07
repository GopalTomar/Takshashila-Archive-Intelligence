"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Logo } from "./Logo";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/archive", label: "Archive" },
  { href: "/search", label: "Search" },
  { href: "/ask", label: "Ask the Archive" },
  { href: "/collections", label: "Collections" },
  { href: "/timeline", label: "Timeline" },
  { href: "/entities", label: "Entities" },
  { href: "/map", label: "Map" },
  { href: "/notes", label: "Research Notes" },
  { href: "/settings", label: "Settings" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  return (
    <div className="min-h-screen flex">
      {/* Left navigation (wine ground; Inter Title Case) */}
      <aside className="w-[220px] shrink-0 bg-wine text-white flex flex-col sticky top-0 h-screen">
        <div className="px-4 py-4 flex items-center gap-2 border-b border-white/15">
          <Logo size={34} />
          <div className="leading-tight">
            <div className="text-[13px] font-medium">Takshashila</div>
            <div className="text-[10px] font-mono tracking-[0.12em] text-white/60 uppercase">
              Archive Intelligence
            </div>
          </div>
        </div>
        <nav className="py-2 flex-1 overflow-y-auto">
          {NAV.map((n) => {
            const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
            return (
              <Link key={n.href} href={n.href} className="navlink" data-active={active}>
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="px-4 py-3 border-t border-white/15 text-[10px] font-mono text-white/50">
          Provenance-first research
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0 bg-paper">{children}</main>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  right,
}: {
  eyebrow?: string;
  title: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="px-10 py-8 rule flex items-end justify-between gap-6">
      <div>
        {eyebrow && <div className="eyebrow mb-2">{eyebrow}</div>}
        <h1 className="text-[40px] leading-[1.1] tracking-[-0.02em]">{title}</h1>
      </div>
      {right}
    </div>
  );
}
