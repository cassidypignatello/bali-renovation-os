import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ["var(--font-display)", "serif"],
        body: ["var(--font-body)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        paper: "var(--paper)",
        "paper-deep": "var(--paper-deep)",
        ink: "var(--ink)",
        "ink-soft": "var(--ink-soft)",
        rule: "var(--rule)",
        palm: "var(--palm)",
        "palm-bright": "var(--palm-bright)",
        clay: "var(--clay)",
        "clay-soft": "var(--clay-soft)",
        sun: "var(--sun)",
        "ink-panel": "var(--ink-panel)",
      },
    },
  },
  plugins: [],
};
export default config;
