import { cn } from '@/shared/utils/cn';

export interface SnbRailItemProps {
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  label: string;
  selected?: boolean;
  /** 아이콘 우상단 점. 발화 조건은 미정이라 표시 여부만 받는다 */
  hasNotification?: boolean;
  onClick?: () => void;
  className?: string;
}

/**
 * 닫힌 SNB의 Rail 아이템. Figma 디자인 시스템 `SNB/menu`의 `type=closed menu`에 대응한다.
 *
 * 선택 배경이 버튼 전체가 아니라 아이콘 칸에만 들어간다 — 라벨이 아이콘 아래에
 * 따로 놓이는 형상이라 배경이 라벨까지 덮으면 알약이 세로로 길어져 보인다.
 */
export default function SnbRailItem({
  Icon,
  label,
  selected = false,
  hasNotification = false,
  onClick,
  className,
}: SnbRailItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={selected ? 'page' : undefined}
      className={cn('flex w-full cursor-pointer flex-col items-center justify-center gap-1', className)}
    >
      <span
        className={cn(
          'relative flex size-9 shrink-0 items-center justify-center rounded-xl transition-colors',
          selected
            ? 'bg-fill-primary-normal-neutral hover:bg-fill-primary-normal-interaction-hover-assistive'
            : 'hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed',
        )}
      >
        <Icon aria-hidden className={cn('size-6', selected ? 'text-icon-primary-normal' : 'text-icon-normal-neutral')} />
        {hasNotification && (
          <span
            data-testid="snb-rail-item-dot"
            className="bg-icon-primary-assistive absolute top-1 right-1 size-1 rounded-full"
          />
        )}
      </span>
      <span
        className={cn(
          'max-w-full truncate text-center text-[11px] leading-[1.5] font-medium',
          selected ? 'text-text-primary-normal' : 'text-text-normal-alternative',
        )}
      >
        {label}
      </span>
    </button>
  );
}
