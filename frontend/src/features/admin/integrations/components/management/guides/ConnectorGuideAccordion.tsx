'use client';

import { useState } from 'react';

import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';
import IconInfoFilled from '@/public/icons/icon/info_filled.svg';

import { CONNECTOR_CONTENT } from '../../../constants/connectorContent';
import type { IntegrationService } from '../../../types/integrationModel';

interface ConnectorGuideAccordionProps {
  service: IntegrationService;
  /** 기존 *GuideSection 컴포넌트. 내용은 손대지 않는다 */
  children: React.ReactNode;
  defaultExpanded?: boolean;
}

/**
 * "○○ 연동 가이드 보기" 접기/펼치기.
 * Figma `16966:26874` — gap 16, radius 12. 헤더 행 실측 `16966:26875`:
 *   info 아이콘 20  `#ff9200`(orange-50) = status-cautionary
 *   라벨            17/SemiBold `#464c53` = heading-medium + text-normal-neutral
 *   화살표 24       `#6d7882`(gray-50)   = icon-normal-neutral
 *   행 정렬 MIN, gap 10 — 화살표는 라벨 **바로 옆**이다. 우측 끝으로 밀지 않는다.
 *
 * 접힘 상태는 Figma에 없다(모든 인스턴스가 펼침 + arrow down) —
 * 접힘 = arrow_right2 는 현행 승계다.
 *
 * 펼쳐지는 내용은 PNG를 static import 하므로, Storybook에서 뜨려면
 * 계획 ①의 next/image 대체(`.storybook/NextImageStub.tsx`)가 살아 있어야 한다.
 */
export default function ConnectorGuideAccordion({
  service,
  children,
  defaultExpanded = false,
}: ConnectorGuideAccordionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const ArrowIcon = expanded ? IconArrowDown : IconArrowRight;

  return (
    <div className="flex flex-col gap-4 rounded-xl">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
        className="flex cursor-pointer items-center gap-2.5 rounded-xl text-left"
      >
        <IconInfoFilled className="text-status-cautionary size-5 shrink-0" />
        <span className="text-heading-medium text-text-normal-neutral">{CONNECTOR_CONTENT[service].guideLabel}</span>
        <ArrowIcon className="text-icon-normal-neutral size-6 shrink-0" />
      </button>

      {expanded && children}
    </div>
  );
}
