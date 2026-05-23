// 전체 패널(헤더+스크롤 영역) 컴포넌트를 패널 폭·고정 높이로 감싸는 컨테이너.

import type { ReactNode } from 'react';

export default function PanelFrame({ children }: { children: ReactNode }) {
  return (
    <div className="bg-fill-strong border-edge-neutral h-160 w-90 overflow-hidden rounded-xl border">
      {children}
    </div>
  );
}
