/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        ink: { 950: "#0b1220", 900: "#111a2e", 800: "#1b2640", 700: "#2a3553", 600: "#475272", 500: "#667090", 400: "#8b94ad", 300: "#b6bccb", 200: "#d9dde6", 100: "#eceff4", 50: "#f6f7fa" },
        brand: { 700: "#1e4fb0", 600: "#2560d0", 500: "#2a78d6", 100: "#e3edfb", 50: "#f1f6fd" },
        ok: { 700: "#0f6b3f", 600: "#15803d", 100: "#dcf3e6", 50: "#effaf3" },
        warn: { 700: "#8a5a00", 600: "#b27300", 100: "#fbeccc", 50: "#fdf7e8" },
        risk: { 700: "#a3262a", 600: "#c2383c", 100: "#f9dcdc", 50: "#fdf0f0" },
        ai: { 700: "#5b3cc4", 600: "#6d4fd6", 100: "#ebe6fb", 50: "#f6f3fe" },
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06)",
        pop: "0 12px 32px -8px rgba(16,24,40,.18), 0 4px 8px -4px rgba(16,24,40,.08)",
      },
      fontSize: { "2xs": ["11px", "16px"] },
    },
  },
  plugins: [],
};
