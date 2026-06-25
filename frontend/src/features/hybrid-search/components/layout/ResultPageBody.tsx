'use client';

// Body shell: px-16, inner max width 355 spacing units (1420px), gap 24px.
// Left result table and right original panel each scroll inside the remaining viewport height.

import type { PropsWithChildren, ReactNode } from 'react';

interface ResultPageBodyProps {
  side: ReactNode;
}

export default function ResultPageBody({ children, side }: PropsWithChildren<ResultPageBodyProps>) {
  return (
    <section className="flex min-h-0 flex-1 justify-center overflow-hidden px-16">
      <div className="flex h-full min-h-0 w-full max-w-355 items-stretch gap-6 overflow-hidden">
        <div className="custom-scrollbar flex min-h-0 min-w-156.25 flex-1 flex-col items-center gap-10 overflow-x-clip overflow-y-auto pt-4 pr-2 pb-30">
          {children}
        </div>
        <aside className="custom-scrollbar border-line-normal-normal flex min-h-0 w-105.75 min-w-105 shrink-0 flex-col overflow-y-auto overscroll-contain border-l">
          {side}
        </aside>
      </div>
    </section>
  );
}
