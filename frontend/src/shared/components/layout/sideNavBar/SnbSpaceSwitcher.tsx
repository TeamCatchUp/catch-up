import { cn } from '@/shared/utils/cn';

export interface SnbSpaceSwitcherProps {
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  /** 닫힘과 미선택에서는 렌더하지 않고 aria-label로만 쓴다 */
  label: string;
  selected?: boolean;
  variant?: 'expanded' | 'closed';
  onClick?: () => void;
  className?: string;
}

/**
 * 홈 ↔ LLM Wiki 모드 스위처. 펼침에서는 선택된 쪽만 라벨을 드러내고 남은 폭을 차지한다.
 * 닫힘에서는 둘 다 정사각이고 선택 쪽만 카드처럼 떠 보인다.
 */
export default function SnbSpaceSwitcher({
  Icon,
  label,
  selected = false,
  variant = 'expanded',
  onClick,
  className,
}: SnbSpaceSwitcherProps) {
  const isClosed = variant === 'closed';
  const showsLabel = !isClosed && selected;

  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={selected ? 'page' : undefined}
      // 라벨이 렌더되지 않을 때만 접근 이름을 따로 준다 — 둘 다 주면 중복으로 읽힌다
      aria-label={showsLabel ? undefined : label}
      className={cn(
        'flex h-9 cursor-pointer items-center justify-center gap-1.5 transition-colors',
        isClosed
          ? cn(
              'size-9 shrink-0 rounded-xl',
              selected
                ? 'border-line-normal-neutral bg-fill-normal-assistive shadow-card border'
                : 'hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed',
            )
          : cn(
              'rounded-full',
              selected
                ? 'bg-fill-primary-normal-neutral hover:bg-fill-primary-normal-interaction-hover-assistive min-w-0 flex-1 px-1.5 py-0.5'
                : 'bg-fill-normal-strong hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed shrink-0 px-5 py-1.5',
            ),
        className,
      )}
    >
      <Icon
        aria-hidden
        className={cn(
          'size-6 shrink-0',
          selected
            ? 'text-icon-normal-strong'
            : // 미선택 아이콘은 펼침에서 한 단계 더 옅다 — 선택 알약 옆에서 대비가 읽혀야 한다
              isClosed
              ? 'text-icon-normal-neutral'
              : 'text-icon-normal-alternative',
        )}
      />
      {showsLabel && <span className="text-heading-small text-text-normal-strong truncate">{label}</span>}
    </button>
  );
}
