/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        premier: {
          DEFAULT: '#006300',
          50:  '#f0fdf0',
          100: '#dcfcdc',
          200: '#bbf7bb',
          300: '#86ef86',
          400: '#4ade4a',
          500: '#22c522',
          600: '#15a315',
          700: '#006300',
          800: '#004d00',
          900: '#003a00',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
