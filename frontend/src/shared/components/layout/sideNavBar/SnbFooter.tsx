import IconAdd from '@/public/icons/icon/add_small.svg';
import IconProfile from '@/public/icons/icon/profile.svg';
import IconSettings from '@/public/icons/icon/settings.svg';
import { DropdownMenu, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

export interface SnbFooterProps {
  userName: string;
  /** 직책. 서버 값이 없으면 소비처가 빈 문자열을 준다 — 대체 문구를 이 컴포넌트가 만들지 않는다 */
  userRole: string;
  onNewClick?: () => void;
  onProfileClick?: () => void;
  onSettingsClick?: () => void;
  /** 전달 시 프로필 버튼이 이 내용을 여는 트리거가 된다. 메뉴 항목은 소비처가 안다 */
  profileMenu?: React.ReactNode;
  /** 온보딩 중처럼 만들 것이 없는 상태에서는 신규 버튼을 내린다 */
  hideNewButton?: boolean;
  className?: string;
}

/**
 * 펼친 SNB 하단. 신규 버튼과 설정이 한 행에 서고, 그 아래가 프로필 행이다.
 * 닫힘에서는 형상이 달라 한 컴포넌트로 합치지 않았다.
 */
export default function SnbFooter({
  userName,
  userRole,
  onNewClick,
  onProfileClick,
  onSettingsClick,
  profileMenu,
  hideNewButton = false,
  className,
}: SnbFooterProps) {
  const profileButton = (
    <button
      type="button"
      onClick={onProfileClick}
      className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 text-left"
    >
      <IconProfile aria-hidden className="border-line-normal-assistive size-9 shrink-0 rounded-xl border" />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-body-small text-text-normal-normal truncate">{userName}</span>
        <span className="text-label-xsmall text-text-normal-alternative truncate">{userRole}</span>
      </span>
    </button>
  );

  return (
    <div className={cn('border-line-normal-neutral flex flex-col gap-1 border-t px-2 pt-2.5', className)}>
      <div className={cn('flex items-center gap-2 px-1', hideNewButton && 'justify-end')}>
        <button
          type="button"
          onClick={onNewClick}
          className={cn(
            'rounded-rounded border-line-normal-normal bg-fill-normal-assistive hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed flex h-9 min-w-0 flex-1 cursor-pointer items-center justify-center gap-1.5 border px-3 py-1.5 transition-colors',
            hideNewButton && 'hidden',
          )}
        >
          <IconAdd aria-hidden className="text-icon-normal-normal size-5 shrink-0" />
          <span className="text-body-small text-text-normal-normal">새 위키</span>
        </button>
        <button
          type="button"
          aria-label="설정"
          onClick={onSettingsClick}
          className="rounded-rounded border-line-normal-normal bg-fill-normal-assistive hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed flex size-9 shrink-0 cursor-pointer items-center justify-center border p-1.5 transition-colors"
        >
          <IconSettings aria-hidden className="text-icon-normal-neutral size-6" />
        </button>
      </div>

      <div className="hover:bg-fill-normal-interaction-hover flex items-center gap-3 rounded-lg px-2.5 py-0.5 transition-colors">
        {profileMenu ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>{profileButton}</DropdownMenuTrigger>
            {profileMenu}
          </DropdownMenu>
        ) : (
          profileButton
        )}
      </div>
    </div>
  );
}
