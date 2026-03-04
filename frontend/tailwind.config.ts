import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    borderRadius: {
      none: "0",
      sm: "0",
      DEFAULT: "0",
      md: "0",
      lg: "0",
      xl: "0",
      "2xl": "0",
      "3xl": "0",
      full: "0",
    },
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        win98: {
          silver: "#c0c0c0",
          darkgray: "#808080",
          black: "#000000",
          white: "#ffffff",
          navy: "#000080",
          blue: "#0000ff",
          red: "#ff0000",
          yellow: "#ffff00",
          green: "#008000",
          teal: "#008080",
          highlight: "#000080",
        },
      },
      fontFamily: {
        sans: ['"MS Sans Serif"', '"Microsoft Sans Serif"', "Arial", "Helvetica", "sans-serif"],
        heading: ['"Arial Black"', '"Impact"', "sans-serif"],
        mono: ['"Courier New"', "Courier", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
