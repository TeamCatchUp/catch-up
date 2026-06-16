import type { ReactNode } from 'react';

interface SectionHeaderProps {
  title: string;
  count: number;
  description: string;
  actions: ReactNode;
}

/** 섹션 헤더 (입장 신청 목록 / 이용자 목록 공통) */
export default function SectionHeader({ title, count, description, actions }: SectionHeaderProps) {
  return (
    <div className="flex items-end justify-between">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-heading-large text-text-normal-normal">
          {title} <span className="text-text-primary-assistive">{count}</span>
        </h2>
        <p className="text-body-small text-text-normal-alternative">{description}</p>
      </div>
      <div className="flex items-center gap-2.5">{actions}</div>
    </div>
  );
}
