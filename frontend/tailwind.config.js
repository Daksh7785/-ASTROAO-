/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#000000',
          secondary: '#05070c',
          card: '#0a0d16',
        },
        border: {
          subtle: '#151b2d',
        },
        accent: {
          blue: '#3b82f6',
          green: '#22c55e',
          orange: '#f97316',
          red: '#ef4444',
          purple: '#a855f7',
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Outfit', 'Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
