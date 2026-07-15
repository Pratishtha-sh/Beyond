/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        blush: '#f5e8dc',
        sky: '#dfeefc',
        mint: '#dff2e8',
        lilac: '#e9e6ff',
        cream: '#fffaf3',
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
