// 콘텐츠/메시지 컴포넌트를 실제 패널 폭(~360px)에 가깝게 감싸는 컨테이너.

import type { ReactNode } from 'react';

export default function PanelWidth({ children }: { children: ReactNode }) {
  return (
    <div className="bg-fill-strong border-edge-neutral w-90 rounded-xl border p-3">{children}</div>
  );
}
