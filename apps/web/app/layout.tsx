import type { Metadata } from "next";
import "./globals.css";
import { ModelProvider } from "./components/ModelContext";
import { Shell } from "./components/Shell";

export const metadata: Metadata = {
  title: "Takshashila Archive Intelligence",
  description: "Provenance-first archival intelligence and grounded AI research.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ModelProvider>
          <Shell>{children}</Shell>
        </ModelProvider>
      </body>
    </html>
  );
}
