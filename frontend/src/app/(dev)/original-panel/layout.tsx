// 갤러리 shell — 좌측 sidebar + 우측 메인 콘텐츠 영역.

import type { ReactNode } from 'react';

import Sidebar from './_components/Sidebar';

export default function OriginalPanelGalleryLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}
