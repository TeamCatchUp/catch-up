import typography from '@tailwindcss/typography';
import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './pages/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      typography: {
        DEFAULT: {
          css: {
            fontFamily: 'Pretendard, system-ui, -apple-system, sans-serif',
          },
        },
      },
    },
  },
  plugins: [typography],
};

export default config;
