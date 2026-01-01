import { Metadata } from 'next';
import '@/styles/globals.css';
import OpenedSideNavbar from '@/components/common/navbar/OpenedSideNavbar';
// import ClosedSideNavbar from '@/components/common/navbar/ClosedSideNavbar';
import TopNabar from '@/components/common/navbar/TopNavbar';
export const metadata: Metadata = { title: 'CATCHUP', description: 'CATCHUP 서비스 홈페이지' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body className="h-screen overflow-hidden">
        <div className="flex h-full">
          <aside className="w-60 flex-shrink-0">
            <OpenedSideNavbar />
          </aside>
          <div className="flex flex-1 flex-col">
            <header className="h-13">
              <TopNabar />
            </header>
            <main className="flex-1 overflow-y-auto">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
