/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Plus Jakarta Sans"', '"Inter"', "ui-sans-serif", "sans-serif"],
        sans: ['"Inter"', "ui-sans-serif", "sans-serif"],
        mono: ['"JetBrains Mono"', '"Fira Code"', "monospace"],
      },
      colors: {
        reroutz: {
          bg:         "#f8fafc",
          panel:      "#ffffff",
          surface:    "#f1f5f9",
          border:     "#e2e8f0",
          borderDark: "#cbd5e1",
          accent:     "#059669",
          accentLight:"#10b981",
          accentSubtle:"#ecfdf5",
          warning:    "#d97706",
          warningSubtle:"#fffbeb",
          danger:     "#e11d48",
          dangerSubtle:"#fff1f2",
          textMain:   "#0f172a",
          textMuted:  "#64748b",
        },
      },
      boxShadow: {
        lightCard: "0 1px 3px 0 rgba(0, 0, 0, 0.06), 0 1px 2px -1px rgba(0, 0, 0, 0.04)",
        lightElevated: "0 10px 15px -3px rgba(0, 0, 0, 0.07), 0 4px 6px -4px rgba(0, 0, 0, 0.03)",
      },
    },
  },
  plugins: [],
};