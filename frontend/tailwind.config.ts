import type { Config } from "tailwindcss";

// Deliberately minimal design tokens — no external component kit.
// The dashboard uses a calm dark palette that suits financial data.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0b1220",
          soft: "#111a2e",
          card: "#141d33",
          hover: "#1a2543",
        },
        line: "#243056",
        ink: {
          DEFAULT: "#e6ebf5",
          muted: "#8590aa",
          faint: "#5b6685",
        },
        brand: {
          DEFAULT: "#6ea8ff",
          muted: "#3a68b0",
          soft: "#1e2b4a",
        },
        good: "#4ade80",
        warn: "#facc15",
        bad: "#f87171",
        info: "#38bdf8",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,0.25), 0 0 0 1px rgba(255,255,255,0.03)",
      },
    },
  },
  plugins: [],
} satisfies Config;
