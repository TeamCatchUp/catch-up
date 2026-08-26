'use client';

import { ThemeProvider as NextThemesProvider } from 'next-themes';

interface ThemeProviderProps {
  children: React.ReactNode;
  /** Storybook 툴바처럼 사용자 선택을 무시하고 한 테마로 고정할 때만 쓴다. */
  forcedTheme?: 'light' | 'dark';
}

export function ThemeProvider({ children, forcedTheme }: ThemeProviderProps) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="system" forcedTheme={forcedTheme} disableTransitionOnChange>
      {children}
    </NextThemesProvider>
  );
}
