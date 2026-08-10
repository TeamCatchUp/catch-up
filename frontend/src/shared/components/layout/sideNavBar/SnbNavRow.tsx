import { cn } from '@/shared/utils/cn';

export interface SnbNavRowProps {
  /** 좌측 아이콘. 생략하면 아이콘 자리를 만들지 않는다 */
  Icon?: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  label: string;
  /** 현재 위치인지 */
  selected?: boolean;
  /** 서버가 준 건수. 미전달이면 배지를 만들지 않는다 — 0건 처리 규칙이 미정이라 컴포넌트가 정하지 않는다 */
  count?: number;
  /** 우측 부가 요소(베타 태그 등) */
  trailing?: React.ReactNode;
  onClick?: () => void;
  className?: string;
}

/**
 * SNB 주 메뉴 행. Figma 디자인 시스템 `SNB/menu`의 `type=Main menu`에 대응한다.
 *
 * 설정 사이드바가 쓰는 {@link ../panels/SnbMenuItem SnbMenuItem}은 같은 컴포넌트 세트의
 * `type=setting`이고 선택 배경이 중립이다. 형상이 같다고 합치면 두 화면 중 하나가
 * 틀린 색을 내게 된다.
 */
export default function SnbNavRow({
  Icon,
  label,
  selected = false,
  count,
  trailing,
  onClick,
  className,
}: SnbNavRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={selected ? 'page' : undefined}
      className={cn(
        'flex h-9 w-full cursor-pointer items-center justify-between gap-3 rounded-lg px-2.5 py-1.5 transition-colors',
        'hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed',
        selected && 'bg-fill-primary-normal-neutral hover:bg-fill-primary-normal-interaction-hover-assistive',
        className,
      )}
    >
      <span className="flex min-w-0 flex-1 items-center gap-3">
        {Icon && (
          <Icon
            aria-hidden
            className={cn('size-5.5 shrink-0', selected ? 'text-icon-primary-normal' : 'text-icon-normal-normal')}
          />
        )}
        <span
          className={cn(
            'text-body-small min-w-0 truncate text-left',
            selected ? 'text-text-primary-normal' : 'text-text-normal-normal',
          )}
        >
          {label}
        </span>
      </span>
      {count !== undefined && (
        <span
          data-testid="snb-nav-row-count"
          className="bg-fill-primary-normal-assistive text-text-primary-normal text-body-xsmall flex h-5 shrink-0 items-center justify-center rounded-md px-0.5"
        >
          {count}
        </span>
      )}
      {trailing}
    </button>
  );
}
