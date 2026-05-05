/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          900: '#0B1437',
          800: '#060B28',
          700: '#0A0E23',
        },
        brand: {
          purple: '#4318FF',
          blue:   '#0075FF',
          cyan:   '#39B8FF',
        },
        accent: {
          green:  '#01B574',
          red:    '#E31A1A',
          yellow: '#FFB547',
          violet: '#A78BFA',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
