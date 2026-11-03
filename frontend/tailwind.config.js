/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Public Sans'", "system-ui", "sans-serif"],
        display: ["'Public Sans'", "system-ui", "sans-serif"],
        mono: ["'Geist Mono'", "ui-monospace", "monospace"],
      },
      colors: {
        // Couleurs pilotées par des variables CSS (thème clair / sombre) : voir src/index.css.
        fond: "rgb(var(--fond) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        relief: "rgb(var(--relief) / <alpha-value>)",
        encre: "rgb(var(--encre) / <alpha-value>)",
        discret: "rgb(var(--discret) / <alpha-value>)",
        trait: "rgb(var(--trait) / <alpha-value>)",
        marque: {
          DEFAULT: "rgb(var(--marque) / <alpha-value>)",
          fonce: "rgb(var(--marque-fonce) / <alpha-value>)",
          doux: "rgb(var(--marque-doux) / <alpha-value>)",
        },
        accent: { DEFAULT: "rgb(var(--accent) / <alpha-value>)", fonce: "rgb(var(--accent-fonce) / <alpha-value>)", doux: "rgb(var(--accent-doux) / <alpha-value>)" },
        institution: "rgb(var(--institution) / <alpha-value>)",
        succes: { DEFAULT: "rgb(var(--succes) / <alpha-value>)", doux: "rgb(var(--succes-doux) / <alpha-value>)" },
        alerte: { DEFAULT: "rgb(var(--alerte) / <alpha-value>)", doux: "rgb(var(--alerte-doux) / <alpha-value>)" },
        danger: { DEFAULT: "rgb(var(--danger) / <alpha-value>)", doux: "rgb(var(--danger-doux) / <alpha-value>)" },
      },
      boxShadow: {
        carte: "0 1px 2px rgb(15 23 42 / 0.04), 0 4px 16px -4px rgb(15 23 42 / 0.06)",
        flottant: "0 12px 40px -12px rgb(15 23 42 / 0.28), 0 2px 6px rgb(15 23 42 / 0.06)",
        anneau: "0 0 0 4px rgb(var(--marque) / 0.14)",
      },
      borderRadius: { xl: "10px", "2xl": "14px" },
      keyframes: {
        miroiter: { "100%": { transform: "translateX(100%)" } },
        apparaitre: { from: { opacity: 0, transform: "translateY(6px)" }, to: { opacity: 1, transform: "none" } },
      },
      animation: {
        miroiter: "miroiter 1.4s infinite",
        apparaitre: "apparaitre .4s cubic-bezier(.2,.8,.2,1) both",
      },
    },
  },
  plugins: [],
};
