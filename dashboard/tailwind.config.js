/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      // No custom color palette. We use Tailwind's built-in `blue` (primary
      // actions, accents) and `slate` (text, borders, surfaces) so utility
      // classes always exist no matter what — `bg-blue-600` will never be
      // missing the way a custom `bg-mint-500` could.
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-ring': 'pulse-ring 1.4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-up': 'fade-up 0.3s ease-out',
        'shimmer': 'shimmer 1.8s infinite',
      },
      keyframes: {
        'pulse-ring': {
          '0%, 100%': { opacity: 1, transform: 'scale(1)' },
          '50%': { opacity: 0.5, transform: 'scale(1.08)' },
        },
        'fade-up': {
          from: { opacity: 0, transform: 'translateY(8px)' },
          to:   { opacity: 1, transform: 'translateY(0)' },
        },
        'shimmer': {
          '0%':   { backgroundPosition: '-600px 0' },
          '100%': { backgroundPosition: '600px 0' },
        },
      },
    },
  },
  plugins: [],
}
