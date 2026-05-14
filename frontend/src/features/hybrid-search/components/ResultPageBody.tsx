'use client';

// Figma 11542:64431 — flex row, 좌측 list / 우측 promo card 320px.
// 외부 vertical container 1388px wide, inner padded area 1260px(x=64 px-16). gap-18(72px), promo w-80(320px).
// pt-4(16px) pb-30(120px).

import type { PropsWithChildren, ReactNode } from 'react';

interface ResultPageBodyProps {
  side: ReactNode;
}

export default function ResultPageBody({ children, side }: PropsWithChildren<ResultPageBodyProps>) {
  return (
    <section className="flex w-full justify-center px-16 pt-4 pb-30">
      <div className="flex w-full max-w-[1260px] gap-18">
        <div className="flex-1">{children}</div>
        <aside className="w-80 shrink-0">{side}</aside>
      </div>
    </section>
  );
}
