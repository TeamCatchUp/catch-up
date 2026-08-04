'use client';

import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';

import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';
import { usePrefersReducedMotion } from '@/shared/hooks/usePrefersReducedMotion';
import { disclosureExpand, disclosureExpandReduced, MotionState } from '@/shared/motion';

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

  /*
   * SNB 밖 경로(예: 커넥터 화면의 "매핑 확인하기" 버튼)로 하위 경로에 진입해도
   * 활성 항목이 보이도록, 하위가 새로 활성화되는 순간 펼친다. 패널이 레이아웃에
   * 상주해 리마운트되지 않으므로 초기값만으로는 부족하다. 활성 상태에서 수동으로
   * 접는 것은 그대로 존중한다.
   */
  const hasActiveChild = items.some((item) => item.href === activeHref);
  const [prevHasActiveChild, setPrevHasActiveChild] = useState(hasActiveChild);
  if (hasActiveChild !== prevHasActiveChild) {
    setPrevHasActiveChild(hasActiveChild);
    if (hasActiveChild) setExpanded(true);
  }

  const ArrowIcon = expanded ? IconArrowDown : IconArrowRight;
  const prefersReducedMotion = usePrefersReducedMotion();

  return (
    <div className="flex flex-col">
      <SnbMenuItem
        Icon={Icon}
        label={label}
        expanded={expanded}
        onClick={() => setExpanded((prev) => !prev)}
        trailing={<ArrowIcon className="text-icon-normal-normal size-5.5 shrink-0" />}
      />

      {/* 하위 목록 — 들여쓰기 + 좌측 세로선으로 상위와의 계층을 표시한다.
          overflow-hidden은 높이가 줄어드는 동안 세로선과 항목이 밖으로 새는 것을 막는다 */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            key="items"
            variants={prefersReducedMotion ? disclosureExpandReduced : disclosureExpand}
            initial={MotionState.Hidden}
            animate={MotionState.Visible}
            exit={MotionState.Exit}
            className="overflow-hidden pl-5.5"
          >
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
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
