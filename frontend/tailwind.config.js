/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Fraunces"', "Georgia", "serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        canvas: "#F3EFE7",   // warm paper
        surface: "#FFFFFF",
        ink: "#1A1714",      // warm near-black
        muted: "#79716A",
        faint: "#A99F92",
        hair: "#E7E0D4",     // warm hairline
        rail: "#26231E",     // warm charcoal (sidebar)
        brand: {
          DEFAULT: "#2D5A4A",  // deep pine
          deep: "#1F4034",
          soft: "#E8EFEA",
        },
        alert: { DEFAULT: "#C4543F", soft: "#F7E9E4" },
        chat: {
          bg: "#E9E2D6",       // warm whatsapp canvas
          out: "#DCEFD6",
          in: "#FFFFFF",
          header: "#2D5A4A",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(26,23,20,0.03), 0 1px 3px rgba(26,23,20,0.05)",
        lift: "0 8px 30px rgba(26,23,20,0.10)",
      },
      keyframes: {
        pulsedot: {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.4", transform: "scale(0.7)" },
        },
      },
      animation: { pulsedot: "pulsedot 1.4s ease-in-out infinite" },
    },
  },
  plugins: [],
}
