import type { Metadata } from 'next';

import QueryProvider from '@/shared/providers/QueryProvider';

import '@/shared/styles/globals.css';

export const metadata: Metadata = {
  title: 'CatchUp',
  description: 'Catchup Service Website',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className="h-screen">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
