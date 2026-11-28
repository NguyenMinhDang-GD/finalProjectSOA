/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        court: {
          DEFAULT: '#142D26',
          deep: '#0D1F1A',
          soft: '#1E4237',
          muted: '#64756B',
        },
        'ball-lime': '#D9F45C',
        'warm-white': '#F6F5EE',
        charcoal: '#202521',
        terracotta: '#C96F48',
      },
      fontFamily: {
        display: [
          '"Bricolage Grotesque Variable"',
          '"Bricolage Grotesque"',
          '"Be Vietnam Pro"',
          'system-ui',
          'sans-serif',
        ],
        sans: [
          '"Be Vietnam Pro"',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'sans-serif',
        ],
        mono: [
          '"JetBrains Mono"',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Consolas',
          'monospace',
        ],
      },
    },
  },
  plugins: [],
};
