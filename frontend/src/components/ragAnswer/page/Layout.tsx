/** 메인/사이드바 2단 레이아웃 컨테이너 */

'use client';

import type { PropsWithChildren } from 'react';

const Layout = ({ children }: PropsWithChildren) => {
  return (
    <div className="flex h-screen w-full">
      {children}
    </div>
  );
};

export default Layout;
