import { cn } from '@/shared/utils/cn';

export interface SnbRailItemProps {
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  label: string;
  selected?: boolean;
  /** 아이콘 우상단 점. 발화 조건은 미정이라 표시 여부만 받는다 */
  hasNotification?: boolean;
  /** 아이콘을 원형 배경 위에 얹는다 — 펼친 SNB의 만들기 행과 같은 구분이다 */
  iconOnDisc?: boolean;
  onClick?: () => void;
  className?: string;
}

/**
 * 닫힌 SNB의 Rail 아이템. 선택 배경은 버튼 전체가 아니라 아이콘 칸에만 들어간다 —
 * 라벨까지 덮으면 알약이 세로로 길어져 보인다.
 */
export default function SnbRailItem({
  Icon,
  label,
  selected = false,
  hasNotification = false,
  iconOnDisc = false,
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
        <span
          className={cn(
            'flex size-6.5 items-center justify-center',
            iconOnDisc && 'bg-fill-normal-interaction-disable rounded-full',
          )}
        >
          <Icon
            aria-hidden
            className={cn('size-6', selected ? 'text-icon-primary-normal' : 'text-icon-normal-neutral')}
          />
        </span>
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
