/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        aviation: {
          dark: '#0A1128',
          card: '#101F42',
          border: '#1E325F',
          blue: '#1C77C3',
          red: '#E63946',
          green: '#2A9D8F',
          yellow: '#E9C46A',
        }
      }
    },
  },
  plugins: [],
}
