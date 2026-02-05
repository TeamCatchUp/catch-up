/** 왼쪽 메인 컨텐츠 영역 */

'use client';

import type { PropsWithChildren } from 'react';

const Main = ({ children }: PropsWithChildren) => {
  return (
    <div className="flex min-w-0 flex-1 flex-col">
      {children}
    </div>
  );
};

export default Main;
