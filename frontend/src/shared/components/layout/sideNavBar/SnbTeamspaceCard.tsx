import { cn } from '@/shared/utils/cn';

export interface SnbTeamspaceCardProps {
  name: string;
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  /** 이름 옆 점. 무엇을 알리는지는 미정이라 표시 여부만 받는다 */
  hasNotification?: boolean;
  /** 미전달 시 버튼이 아닌 표시용 마크업으로 렌더한다 */
  onClick?: () => void;
  className?: string;
}

/**
 * 현재 팀스페이스 카드. Figma 디자인 시스템 `SNB/Dropdown`에 대응한다.
 *
 * 이름은 Dropdown이지만 시안에 열림 상태도 셰브런도 없다. 전환 컨트롤인지
 * 현재 위치 표시인지 결정되기 전까지 눌리는 것처럼 보이게 만들지 않는다 —
 * `onClick`을 받은 경우에만 버튼이 된다.
 */
export default function SnbTeamspaceCard({
  name,
  Icon,
  hasNotification = false,
  onClick,
  className,
}: SnbTeamspaceCardProps) {
  const body = (
    <>
      <span className="text-body-xsmall text-text-normal-alternative block text-left">팀스페이스</span>
      <span className="flex items-center gap-3">
        <span className="relative flex size-6 shrink-0 items-center justify-center">
          <Icon aria-hidden className="text-icon-normal-normal size-5.5" />
          {hasNotification && (
            <span
              data-testid="snb-teamspace-dot"
              className="bg-icon-primary-assistive absolute top-0 right-0 size-1.5 rounded-full"
            />
          )}
        </span>
        <span className="text-body-small text-text-normal-normal min-w-0 truncate text-left">{name}</span>
      </span>
    </>
  );

  const shell = cn('border-line-normal-neutral flex w-full flex-col gap-1.5 rounded-xl border px-2.5 py-1.5', className);

  if (!onClick) {
    return <div className={shell}>{body}</div>;
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        shell,
        // hover/pressed는 solid 토큰으로 상대 순서만 지킨다(Figma는 알파 오버레이)
        'hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed cursor-pointer transition-colors',
      )}
    >
      {body}
    </button>
  );
}
