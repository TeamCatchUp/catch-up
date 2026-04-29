'use client';

import { type ComponentType, memo, type SVGProps } from 'react';

interface EntityChipProps {
  icon: ComponentType<SVGProps<SVGSVGElement>>;
}

/** 채널/도큐먼트 스페이스 등 entity를 표현하는 작은 아이콘 chip (회색 배경 + 1px border + rounded). */
function EntityChip({ icon: Icon }: EntityChipProps) {
  return (
    <span className="border-edge-neutral bg-fill-strong text-content-alternative rounded-md2 inline-flex shrink-0 items-center justify-center border p-0.5">
      <Icon className="size-4" />
    </span>
  );
}

export default memo(EntityChip);
