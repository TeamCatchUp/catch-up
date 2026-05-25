'use client';

// Figma body shell: px-16 / pb-30, inner max width 1420px, gap 24px.
// Left result table grows from a 625px minimum; right original panel stays fixed at 423px.
// The right panel remains always visible and scrolls internally when its content overflows.

import type { PropsWithChildren, ReactNode } from 'react';

interface ResultPageBodyProps {
  side: ReactNode;
}

export default function ResultPageBody({ children, side }: PropsWithChildren<ResultPageBodyProps>) {
  return (
    <section className="flex w-full justify-center px-16 pb-30">
      <div className="flex w-full max-w-[1420px] items-start gap-6">
        <div className="flex min-w-156.25 flex-1 flex-col items-center gap-10 overflow-x-clip overflow-y-auto py-4">
          {children}
        </div>
        <aside className="custom-scrollbar border-edge-normal max-h-340 w-105.75 shrink-0 overflow-y-auto overscroll-contain border-l">
          {side}
        </aside>
      </div>
    </section>
  );
}
