import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Warm editorial palette
        canvas: {
          DEFAULT: 'var(--canvas)',
          alt: 'var(--canvas-alt)',
        },
        surface: {
          DEFAULT: 'var(--surface)',
          raised: 'var(--surface-raised)',
          overlay: 'var(--surface-overlay)',
        },
        border: {
          DEFAULT: 'var(--border)',
          muted: 'var(--border-muted)',
        },
        ink: {
          DEFAULT: 'var(--ink)',
          muted: 'var(--ink-muted)',
          faint: 'var(--ink-faint)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          hover: 'var(--accent-hover)',
          muted: 'var(--accent-muted)',
          ink: 'var(--accent-ink)',
        },
        positive: {
          DEFAULT: 'var(--positive)',
          muted: 'var(--positive-muted)',
        },
        caution: {
          DEFAULT: 'var(--caution)',
          muted: 'var(--caution-muted)',
        },
        negative: {
          DEFAULT: 'var(--negative)',
          muted: 'var(--negative-muted)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],        // 11px
      },
      borderRadius: {
        'sm': '4px',
        'DEFAULT': '6px',
        'md': '8px',
        'lg': '10px',
        'xl': '14px',
      },
      boxShadow: {
        'subtle': '0 1px 2px 0 rgba(0,0,0,0.04)',
        'lifted': '0 2px 8px -2px rgba(0,0,0,0.08), 0 1px 2px -1px rgba(0,0,0,0.04)',
        'modal': '0 16px 48px -12px rgba(0,0,0,0.20), 0 4px 16px -4px rgba(0,0,0,0.08)',
      },
      transitionDuration: {
        '150': '150ms',
      },
    },
  },
  plugins: [],
};

export default config;
