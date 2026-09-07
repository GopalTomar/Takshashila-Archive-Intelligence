import type { Config } from "tailwindcss";

// Takshashila design language tokens.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        wine: { DEFAULT: "#620d3c", dark: "#4a0a2e", soft: "#f5e6ec" },
        gold: { DEFAULT: "#f1a222", soft: "#fcf0d9" },
        paper: "#FFFFFF",
        deep: "#F7F5F2",
        ink: {
          DEFAULT: "#171413",
          70: "rgba(23,20,19,0.70)",
          50: "rgba(23,20,19,0.50)",
          20: "rgba(23,20,19,0.16)",
          10: "rgba(23,20,19,0.08)",
        },
        positive: "#2f6b4a",
        negative: "#a3282d",
        cat: {
          1: "#620d3c", 2: "#f1a222", 3: "#2f6b6b",
          4: "#b8809f", 5: "#4a5a7a", 6: "#a8703a",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "system-ui", "sans-serif"],
        mono: ["'Roboto Mono'", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: { none: "0", DEFAULT: "0" },
      maxWidth: { content: "1240px" },
    },
  },
  plugins: [],
};
export default config;
