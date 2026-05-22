'use client';

// flex row, 좌측 결과 list 625px / gap 24px / 우측 원문 패널 423px.
// 우측 패널은 상시 노출 — side 슬롯에 OriginalPanel 이 항상 들어온다.
// 좌측 list w-156.25(625px) + gap-6(24px) + panel w-105.75(423px) = 1072px.
// pt-4(16px) pb-30(120px).

import type { PropsWithChildren, ReactNode } from 'react';

interface ResultPageBodyProps {
  side: ReactNode;
}

export default function ResultPageBody({ children, side }: PropsWithChildren<ResultPageBodyProps>) {
  return (
    <section className="flex w-full justify-center px-16 pt-4 pb-30">
      <div className="flex w-full max-w-[1440px] gap-6">
        <div className="w-156.25 shrink-0">{children}</div>
        <aside className="w-105.75 shrink-0">{side}</aside>
      </div>
    </section>
  );
}
