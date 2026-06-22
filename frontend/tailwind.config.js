/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        wa: {
          green: "#25D366",
          dark: "#075E54",
          teal: "#128C7E",
          bg: "#ECE5DD",
          bubble: "#DCF8C6",
        },
      },
    },
  },
  plugins: [],
}
