/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#fafaf7',
        surface: '#f3f0e8',
        ink: '#1a1a1a',
        muted: '#5c5852',
        border: '#d4d0c4',
        accent: {
          DEFAULT: '#b85450',
          soft: '#f5e6e3',
        },
        good: {
          DEFAULT: '#2d6e3e',
          soft: '#e3ede5',
        },
        warn: {
          DEFAULT: '#a07020',
          soft: '#f4ead4',
        },
        code: {
          bg: '#2a2825',
          ink: '#e8e4d8',
        },
      },
      fontFamily: {
        serif: ['Georgia', '"Times New Roman"', 'serif'],
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', '"SF Mono"', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};
