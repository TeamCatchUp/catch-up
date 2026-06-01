// 한 케이스 — 라벨 + 렌더 결과.

import type { ReactNode } from 'react';

interface CaseProps {
  label: string;
  children: ReactNode;
}

export default function Case({ label, children }: CaseProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-body-xsmall text-content-assistive font-medium">{label}</span>
      {children}
    </div>
  );
}
