// 상담·고객 정보의 좌측 라벨 클러스터 — 138px 고정 width + 아이콘 + 텍스트.
// ConsultationInfo·CustomerInfo 두 컴포넌트가 동일 패턴을 공유하기 위한 feature-local 컴포넌트.

import type { ComponentType, SVGProps } from 'react';

interface InfoFieldLabelProps {
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  text: string;
}

export default function InfoFieldLabel({ icon: Icon, text }: InfoFieldLabelProps) {
  return (
    <span className="flex w-[138px] shrink-0 items-center gap-4">
      <Icon className="text-icon-normal-neutral h-5.5 w-5.5" />
      <span className="text-body-small text-text-normal-alternative">{text}</span>
    </span>
  );
}
