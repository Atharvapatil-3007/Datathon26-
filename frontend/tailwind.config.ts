import type { Config } from "tailwindcss";

/**
 * Design tokens for the platform.
 *
 * Two token layers exist:
 *   1. Legacy aliases (bg, ink, line, brand, good, warn, bad, info) — kept
 *      for backwards compatibility with existing components. Tuned slightly
 *      toward a deeper, more restrained navy palette.
 *   2. Semantic aliases (surface, border, text-*, accent) exposed so new
 *      components can express intent rather than raw colors.
 *
 * All values are chosen for a premium, minimal financial-intelligence look:
 * deep navy backgrounds, near-white surfaces on top for high contrast, muted
 * greys for typography, and restrained accent colors that only communicate
 * meaning (positive / warning / negative).
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // ---------- legacy aliases (retuned, same names) ----------
        bg: {
          DEFAULT: "#070b18",
          soft: "#0d1425",
          card: "#101a33",
          hover: "#182541",
          elev: "#152039",
        },
        line: {
          DEFAULT: "#1e2a4a",
          strong: "#2a3a63",
          soft: "#182241",
        },
        ink: {
          DEFAULT: "#eef2ff",
          muted: "#94a3c4",
          faint: "#5c6885",
        },
        brand: {
          DEFAULT: "#7aa8ff",
          muted: "#4478d6",
          soft: "#152647",
          strong: "#a9c5ff",
        },
        good: {
          DEFAULT: "#4ade80",
          soft: "#0f2a1e",
        },
        warn: {
          DEFAULT: "#facc15",
          soft: "#2b230a",
        },
        bad: {
          DEFAULT: "#f87171",
          soft: "#2c1416",
        },
        info: {
          DEFAULT: "#38bdf8",
          soft: "#0d2233",
        },
        accent: {
          DEFAULT: "#a78bfa", // subtle indigo used for AI / insights
          soft: "#1c1a3a",
        },

        // ---------- semantic aliases (new) ----------
        surface: {
          DEFAULT: "#101a33",
          alt: "#0d1425",
          raised: "#152039",
          hover: "#182541",
        },
        border: {
          DEFAULT: "#1e2a4a",
          strong: "#2a3a63",
          soft: "#182241",
        },
        text: {
          primary: "#eef2ff",
          secondary: "#94a3c4",
          muted: "#5c6885",
          inverted: "#0b1220",
        },
      },
      fontFamily: {
        sans: [
          "Fira Sans",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        display: [
          "Fira Sans",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
        mono: [
          "Fira Code",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      fontSize: {
        // Compact hierarchy tuned for data-dense dashboards.
        "display-lg": ["2.75rem", { lineHeight: "1.05", letterSpacing: "-0.02em", fontWeight: "600" }],
        display: ["2.25rem", { lineHeight: "1.1", letterSpacing: "-0.02em", fontWeight: "600" }],
        h1: ["1.75rem", { lineHeight: "1.2", letterSpacing: "-0.015em", fontWeight: "600" }],
        h2: ["1.25rem", { lineHeight: "1.3", letterSpacing: "-0.01em", fontWeight: "600" }],
        h3: ["1rem", { lineHeight: "1.4", fontWeight: "600" }],
        metric: ["1.875rem", { lineHeight: "1", letterSpacing: "-0.02em", fontWeight: "600" }],
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1rem",
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,0.35), 0 0 0 1px rgba(255,255,255,0.03)",
        elev: "0 6px 24px -8px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04)",
        glow: "0 0 0 1px rgba(122,168,255,0.35), 0 8px 30px -6px rgba(122,168,255,0.25)",
        insetTop: "inset 0 1px 0 0 rgba(255,255,255,0.04)",
      },
      backgroundImage: {
        "brand-gradient":
          "linear-gradient(135deg, rgba(122,168,255,0.15) 0%, rgba(167,139,250,0.10) 100%)",
        "hero-gradient":
          "radial-gradient(1200px 400px at 10% 0%, rgba(122,168,255,0.10), transparent 60%), radial-gradient(900px 400px at 90% 0%, rgba(167,139,250,0.08), transparent 55%)",
        "grid-fade":
          "linear-gradient(to bottom, rgba(122,168,255,0.05), transparent 70%)",
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseSoft: {
          "0%,100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s infinite",
        fadeIn: "fadeIn 220ms ease-out",
        pulseSoft: "pulseSoft 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
