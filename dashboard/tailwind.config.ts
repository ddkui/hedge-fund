import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0a0a0f",
        surface: "#13131a",
        border: "#1e1e2e",
        accent: "#00d4aa",
        danger: "#ff4757",
        warning: "#ffa502",
        muted: "#6b7280",
      },
    },
  },
  plugins: [],
};
export default config;
