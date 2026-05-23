'use client';

// flex row, 좌측 결과 list 625px / gap 24px / 우측 원문 패널 423px.
// 우측 패널은 상시 노출 — side 슬롯에 OriginalPanel 이 항상 들어온다.
// 좌측 list w-156.25(625px) + gap-6(24px) + panel w-105.75(423px) = 1072px.
// 섹션 top padding 없음 — 우측 패널 좌측 border 가 header 하단 border 까지 닿도록.
// 좌측 컬럼은 자체 pt-4 로 상단 여백 확보, 우측 패널 내용은 OriginalPanelContent 의 py-4 가 담당.
// 우측 패널 max-h-340(1360px) — 좌측 카드 10개 정도의 높이. 메시지가 더 길면 메시지 영역만 내부 스크롤.

import type { PropsWithChildren, ReactNode } from 'react';

interface ResultPageBodyProps {
  side: ReactNode;
}

export default function ResultPageBody({ children, side }: PropsWithChildren<ResultPageBodyProps>) {
  return (
    <section className="flex w-full justify-center px-16 pb-30">
      <div className="flex w-full max-w-[1440px] gap-6">
        <div className="w-156.25 shrink-0 pt-4">{children}</div>
        <aside className="border-edge-neutral max-h-340 w-105.75 shrink-0 overflow-hidden border-l">
          {side}
        </aside>
      </div>
    </section>
  );
}
