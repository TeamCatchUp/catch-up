'use client';

import { useState } from 'react';

import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';

import SnbMenuItem from './SnbMenuItem';

export interface SettingsNavGroupChild {
  name: string;
  href: string;
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
}

interface SettingsNavGroupProps {
  label: string;
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  /** 하위 메뉴 데이터. React children이 아니므로 이름을 items로 둔다 */
  items: SettingsNavGroupChild[];
  /** 현재 활성 경로. 하위 항목의 selected 판정에 쓴다 */
  activeHref: string | null;
  onSelect: (href: string) => void;
  /** 초기 펼침 여부. 하위에 활성 항목이 있으면 호출 측이 true를 넘긴다 */
  defaultExpanded?: boolean;
}

/**
 * 하위 메뉴를 가진 설정 사이드바 항목.
 * 조직 협업툴 연동과 멤버 관리 두 곳에서 쓴다.
 */
export default function SettingsNavGroup({
  label,
  Icon,
  items,
  activeHref,
  onSelect,
  defaultExpanded = false,
}: SettingsNavGroupProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const ArrowIcon = expanded ? IconArrowDown : IconArrowRight;

  return (
    <div className="flex flex-col">
      <SnbMenuItem
        Icon={Icon}
        label={label}
        expanded={expanded}
        onClick={() => setExpanded((prev) => !prev)}
        trailing={<ArrowIcon className="text-icon-normal-normal size-5.5 shrink-0" />}
      />

      {/* 하위 목록 — 들여쓰기 + 좌측 세로선으로 상위와의 계층을 표시한다 */}
      {expanded && (
        <div className="pl-5.5">
          <div className="border-line-normal-neutral flex flex-col border-l pl-5.5">
            {items.map((child) => (
              <SnbMenuItem
                key={child.href}
                Icon={child.Icon}
                label={child.name}
                selected={activeHref === child.href}
                onClick={() => onSelect(child.href)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
