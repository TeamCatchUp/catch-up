import type { Metadata } from 'next';
import '@/styles/globals.css';
import SideNavbar from '@/components/common/sideNavbar/SideNavbar';

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
        {/* overflow-hidden */}
        <div className="flex h-full">
          <aside>
            <SideNavbar />
          </aside>
          <div className="flex flex-1 flex-col">
            <main className="flex-1 overflow-auto">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
