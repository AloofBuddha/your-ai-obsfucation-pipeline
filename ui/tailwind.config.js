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
        xray: {
          bg: '#1f1d1a',
          header: '#16140f',
          minimap: '#1a1815',
          panel: '#1c1a17',
          'panel-crossed': '#22201b',
          banner: '#1f1d18',
          'banner-crossed': '#2a2018',
          'banner-pivot': '#241f17',
          'banner-error': '#22181a',
          inset: '#181613',
          'inset-deep': '#252119',
          border: '#2e2a22',
          'border-soft': '#3a352b',
          'border-strong': '#4a4438',
          ink: '#e8e4d8',
          text: '#c8c2b1',
          muted: '#a59f8d',
          fade: '#7a766a',
          dim: '#5a564d',
          warm: '#c08070',
        },
      },
      fontFamily: {
        serif: ['Georgia', '"Times New Roman"', 'serif'],
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', '"SF Mono"', 'Menlo', 'monospace'],
      },
      keyframes: {
        'xray-pulse': {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.45', transform: 'scale(0.8)' },
        },
        'xray-spin': {
          to: { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        'xray-pulse': 'xray-pulse 1.2s ease-in-out infinite',
        'xray-spin': 'xray-spin 1.1s linear infinite',
      },
    },
  },
  plugins: [],
};
