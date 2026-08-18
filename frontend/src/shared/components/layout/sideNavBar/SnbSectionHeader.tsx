import type { ComponentType, SVGProps } from 'react';

import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconArrowRight2 from '@/public/icons/icon/arrow_right2.svg';
import { cn } from '@/shared/utils/cn';

/** 에이전트 섹션 머리글에 붙는 회색 알약. 머리글 안에서만 쓰인다 */
export function SnbBetaBadge() {
  return (
    <span className="bg-fill-normal-interaction-hover text-text-normal-alternative inline-flex h-5 shrink-0 items-center justify-center rounded px-1 text-[12px] leading-[1.5] font-medium">
      베타
    </span>
  );
}

/** 머리글 우측 액션 버튼. 무엇을 하는지는 소비처가 label·onClick으로 정한다 */
export function SnbSectionAction({
  label,
  Icon,
  onClick,
  active = false,
}: {
  label: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
  onClick: (trigger: HTMLElement) => void;
  /** 이 버튼이 연 메뉴가 떠 있는가 */
  active?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-expanded={active || undefined}
      onClick={(event) => onClick(event.currentTarget)}
      className={cn(
        'text-icon-normal-neutral flex size-5.5 shrink-0 cursor-pointer items-center justify-center rounded-full',
        active ? 'bg-fill-normal-interaction-pressed' : 'hover:bg-fill-normal-interaction-hover',
      )}
    >
      <Icon aria-hidden className="size-4.5" />
    </button>
  );
}

export interface SnbSectionHeaderProps {
  label: string;
  /** 라벨 우측 슬롯. 지금 쓰이는 것은 베타 배지 하나뿐이다 */
  badge?: React.ReactNode;
  /** 전달 시에만 접기 셰브런이 생긴다. 펼침 여부는 소비처가 들고 있다 */
  onToggleCollapse?: () => void;
  /** 셰브런 방향. 접기 가능한 머리글에서만 의미가 있다 */
  expanded?: boolean;
  /** 우측 액션 슬롯. 무엇을 하는 버튼인지는 소비처가 안다 */
  actions?: React.ReactNode;
  /** 액션이 연 메뉴가 떠 있는가. 그 동안은 hover 없이도 액션이 유지된다 */
  actionsOpen?: boolean;
  /** 전달 시에만 라벨이 버튼이 된다. 접기와 함께 오면 접기는 셰브런이 맡는다 */
  onClick?: () => void;
  className?: string;
}

/** SNB 섹션 머리글. 에이전트·즐겨찾기·최근 질문·프로젝트가 공유한다 */
export default function SnbSectionHeader({
  label,
  badge,
  onToggleCollapse,
  expanded = true,
  actions,
  actionsOpen = false,
  onClick,
  className,
}: SnbSectionHeaderProps) {
  const collapsible = onToggleCollapse !== undefined;
  // 한 버튼이 두 동작을 가질 수 없어, 라벨 클릭이 있으면 접기를 셰브런 버튼으로 뗀다
  const chevronIsButton = collapsible && onClick !== undefined;
  const ChevronIcon = expanded ? IconArrowDown : IconArrowRight2;
  const gapClass = badge ? 'gap-1.5' : 'gap-0.5';
  /*
   * 셰브런·액션은 hover·focus에서만 나타난다. 평소에는 라벨만 남는다.
   * 메뉴가 열린 동안 숨기면 앵커가 0×0이 되어 팝오버가 좌상단으로 튄다.
   */
  const revealClass = cn(
    'group-focus-within/header:flex group-hover/header:flex',
    actionsOpen ? 'flex' : 'hidden',
  );

  const labelContent = (
    <>
      <span className="text-body-xsmall text-text-normal-alternative min-w-0 truncate text-left">{label}</span>
      {badge}
    </>
  );

  // 남는 가로 공간은 라벨 쪽이 먹는다 — 액션은 오른쪽 끝에 붙는다
  const leadClass = cn('flex min-w-0 flex-1 items-center', gapClass);

  let lead: React.ReactNode;
  if (chevronIsButton) {
    lead = (
      <div className={leadClass}>
        <button type="button" onClick={onClick} className={cn('flex min-w-0 cursor-pointer items-center', gapClass)}>
          {labelContent}
        </button>
        <button
          type="button"
          aria-label={`${label} ${expanded ? '접기' : '펼치기'}`}
          aria-expanded={expanded}
          onClick={onToggleCollapse}
          className={cn(
            'text-icon-normal-alternative hover:bg-fill-normal-interaction-hover size-4.5 shrink-0 cursor-pointer items-center justify-center rounded-full',
            revealClass,
          )}
        >
          <ChevronIcon aria-hidden className="size-4.5" />
        </button>
      </div>
    );
  } else if (collapsible) {
    lead = (
      <button
        type="button"
        aria-expanded={expanded}
        onClick={onToggleCollapse}
        className={cn(leadClass, 'cursor-pointer')}
      >
        {labelContent}
        <ChevronIcon aria-hidden className={cn('text-icon-normal-alternative size-4.5 shrink-0', revealClass)} />
      </button>
    );
  } else if (onClick) {
    lead = (
      <button type="button" onClick={onClick} className={cn(leadClass, 'cursor-pointer')}>
        {labelContent}
      </button>
    );
  } else {
    lead = <span className={leadClass}>{labelContent}</span>;
  }

  return (
    <div
      data-slot="snb-section-header"
      className={cn(
        'group/header flex h-7.5 items-center gap-0.5 rounded-lg px-2.5',
        // 행과 달리 머리글 hover는 알파 오버레이가 아니라 Fill/Normal/Strong 단색이다
        (collapsible || onClick) &&
          'hover:bg-fill-normal-strong has-[button:active]:bg-fill-normal-interaction-pressed transition-colors',
        className,
      )}
    >
      {lead}
      {/* 액션은 라벨 버튼의 형제다 — 중첩하면 클릭이 머리글 동작으로 샌다 */}
      {actions !== undefined && <div className={cn('shrink-0 items-center gap-0.5', revealClass)}>{actions}</div>}
    </div>
  );
}
