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
  /** 갈 곳이 아직 없는 메뉴. 시안에 disabled 상태가 없어 리포 버튼 관례를 따른다 */
  disabled?: boolean;
  /** 아이콘을 원형 배경 위에 얹는다 — "새 채팅"처럼 만들기 행을 다른 메뉴와 구분한다 */
  iconOnDisc?: boolean;
  onClick?: () => void;
  className?: string;
}

/**
 * SNB 주 메뉴 행. 형상이 같은 {@link ../panels/SnbMenuItem SnbMenuItem}과 합치지 않는다 —
 * 그쪽은 선택 배경이 중립이라 합치면 두 화면 중 하나가 틀린 색을 낸다.
 */
export default function SnbNavRow({
  Icon,
  label,
  selected = false,
  count,
  trailing,
  disabled = false,
  iconOnDisc = false,
  onClick,
  className,
}: SnbNavRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-current={selected ? 'page' : undefined}
      className={cn(
        'flex h-9 w-full items-center justify-between gap-3 rounded-lg px-2.5 py-1.5 transition-colors',
        disabled
          ? 'cursor-not-allowed'
          : cn(
              'cursor-pointer hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed',
              selected && 'bg-fill-primary-normal-neutral hover:bg-fill-primary-normal-interaction-hover-assistive',
            ),
        className,
      )}
    >
      <span className="flex min-w-0 flex-1 items-center gap-3">
        {Icon && (
          <span
            className={cn(
              'flex size-5.5 shrink-0 items-center justify-center',
              iconOnDisc && 'bg-fill-normal-interaction-disable rounded-full',
            )}
          >
            <Icon
              aria-hidden
              className={cn(
                iconOnDisc ? 'size-4' : 'size-5.5',
                disabled
                  ? 'text-icon-normal-assistive'
                  : selected
                    ? 'text-icon-primary-normal'
                    : iconOnDisc
                      ? 'text-icon-normal-neutral'
                      : 'text-icon-normal-normal',
              )}
            />
          </span>
        )}
        <span
          className={cn(
            'text-body-small min-w-0 truncate text-left',
            disabled
              ? 'text-text-normal-assistive'
              : selected
                ? 'text-text-primary-normal'
                : 'text-text-normal-normal',
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
