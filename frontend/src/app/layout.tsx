import type { Metadata } from 'next';

import QueryProvider from '@/shared/providers/QueryProvider';
import { ThemeProvider } from '@/shared/providers/ThemeProvider';

import '@/shared/styles/globals.css';

export const metadata: Metadata = {
  title: 'CatchUp',
  description: 'Catchup Service Website',
  icons: {
    icon: '/icons/favicon.svg',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body className="h-screen">
        <ThemeProvider>
          <QueryProvider>{children}</QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
