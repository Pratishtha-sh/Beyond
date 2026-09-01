/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        'pastel-pink': '#f9c6d0',
        'pastel-pink-light': '#fde8ed',
        'pastel-blue': '#b8d8f8',
        'pastel-blue-light': '#dceefb',
        'pastel-green': '#92c9b1',
        'pastel-green-light': '#b3e0d2',
        'pastel-cream': '#fef9f4',
        // Keep old aliases for backward compat in case any dark-mode references remain
        cream: '#fef9f4',
        sky: '#dceefb',
        mint: '#b3e0d2',
        lilac: '#fde8ed',
        blush: '#f9c6d0',
      },
      boxShadow: {
        soft: '0 20px 60px -20px rgba(76, 94, 115, 0.24)',
      },
      animation: {
        float: 'float 6s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
      },
    },
  },
  plugins: [],
};
