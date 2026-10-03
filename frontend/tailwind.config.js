/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0f172a",
        panel: "#162036",
        panel2: "#1d2a47",
        accent: "#f59e0b",
        // Cian de la mitad "digital" del logo (AI Sentinel) -- se usa en detalles
        // de marca (gradientes, glow, landing), no reemplaza al accent principal.
        accent2: "#38bdf8",
        danger: "#ef4444",
        ok: "#22c55e",
        warn: "#eab308"
      }
    }
  },
  plugins: []
};
