/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        surface: {
          page: 'var(--surface-page)',
          1: 'var(--surface-1)',
          2: 'var(--surface-2)',
          3: 'var(--surface-3)',
        },
        edge: {
          subtle: 'var(--border-subtle)',
          strong: 'var(--border-strong)',
        },
        ink: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
          inverse: 'var(--text-inverse)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          hover: 'var(--accent-hover)',
          soft: 'var(--accent-soft)',
        },
        status: {
          good: 'var(--status-good)',
          'good-bg': 'var(--status-good-bg)',
          warn: 'var(--status-warn)',
          'warn-bg': 'var(--status-warn-bg)',
          critical: 'var(--status-critical)',
          'crit-bg': 'var(--status-crit-bg)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      letterSpacing: { tightest: '-0.03em' },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
      },
      maxWidth: { content: '72rem' },
    },
  },
  plugins: [],
}
