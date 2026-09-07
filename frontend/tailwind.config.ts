import type {Config} from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{vue,ts}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef2ff",
          500: "#4f46e5",
          600: "#4338ca"
        }
      }
    }
  },
  plugins: []
} satisfies Config;
