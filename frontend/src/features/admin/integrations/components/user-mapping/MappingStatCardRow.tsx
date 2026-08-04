'use client';

import type { ComponentType, SVGProps } from 'react';

import MappingStatCard from './MappingStatCard';

export interface MappingStatItem {
  /** 카드 식별자 — 통계 API 키(jira/github/slack/confluence/channel_talk) */
  key: string;
  Logo: ComponentType<SVGProps<SVGSVGElement>>;
  name: string;
  percent: number;
  countLabel: string;
}

interface MappingStatCardRowProps {
  items: readonly MappingStatItem[];
  /** 선택된 카드 key. null이면 전체 */
  selected: string | null;
  onToggle: (key: string) => void;
}

/**
 * 계정 등록 상태 카드 행.
 * Figma `17240:74853` — 카드 5장이 1040을 5등분(208), 카드 사이 구분선은 없다.
 * 통계는 5종(Jira·Confluence 분리)이고 표 필터는 4종(atlassian 합침)이라
 * 카드 key → 표 필터 매핑은 배선(호출부)이 정한다.
 */
export default function MappingStatCardRow({ items, selected, onToggle }: MappingStatCardRowProps) {
  return (
    <div className="border-line-normal-neutral flex overflow-x-auto rounded-xl border">
      {items.map((item) => (
        <MappingStatCard
          key={item.key}
          Logo={item.Logo}
          name={item.name}
          percent={item.percent}
          countLabel={item.countLabel}
          selected={selected === item.key}
          onToggle={() => onToggle(item.key)}
        />
      ))}
    </div>
  );
}
