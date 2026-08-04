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
}

/**
 * 계정 등록 상태 카드 행.
 * Figma `17300:80304` — 흰 배경 + `line/normal/neutral` 1px + radius 12,
 * 카드 5장이 1040을 5등분(208), 카드 사이 gap 0. 구분은 두 번째 카드부터 걸린
 * 왼쪽 선이 만든다(카드가 담당).
 *
 * 표시 전용이다 — 카드를 눌러도 아래 표는 바뀌지 않는다(사용자 결정 2026-08-04).
 * 통계는 5종(Jira·Confluence 분리)이고 표 열은 4종(atlassian 합침)이라
 * 애초에 1:1로 대응하지도 않는다.
 */
export default function MappingStatCardRow({ items }: MappingStatCardRowProps) {
  return (
    <div className="border-line-normal-neutral bg-fill-normal-normal flex flex-wrap overflow-hidden rounded-xl border">
      {items.map((item) => (
        <MappingStatCard
          key={item.key}
          Logo={item.Logo}
          name={item.name}
          percent={item.percent}
          countLabel={item.countLabel}
        />
      ))}
    </div>
  );
}
