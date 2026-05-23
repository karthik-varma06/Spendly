/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      boxShadow: {
        soft: '0 10px 30px rgba(0,0,0,0.08)',
      },
      backgroundImage: {
        hero: 'linear-gradient(135deg, rgba(59,130,246,0.14), rgba(16,185,129,0.14))'
      }
    },
  },
  plugins: [],
}
