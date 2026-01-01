import { Metadata } from 'next';
import '@/styles/globals.css';
import OpenedSideNavbar from '@/components/common/sideNavbar/OpenedSideNavbar';
// import ClosedSideNavbar from '@/components/common/sideNavbar/ClosedSideNavbar';
import TopNavbar from '@/components/common/topNavbar/TopNavbar';

export const metadata: Metadata = {
  title: 'CATCHUP',
  description: 'CATCHUP 서비스 홈페이지',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body className="h-screen">
        <div className="flex h-full">
          <aside className="w-60 flex-shrink-0">
            <OpenedSideNavbar />
          </aside>
          <div className="flex flex-1 flex-col">
            <header className="h-[53px] flex-shrink-0">
              <TopNavbar />
            </header>
            <main className="flex-1 overflow-y-auto">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
