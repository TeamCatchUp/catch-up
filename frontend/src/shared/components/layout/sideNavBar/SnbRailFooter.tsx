import IconProfile from '@/public/icons/icon/profile.svg';
import IconSettings from '@/public/icons/icon/settings.svg';
import { DropdownMenu, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

export interface SnbRailFooterProps {
  /** 화면에 보이지 않고 프로필 버튼의 접근 이름으로 쓴다 */
  userName: string;
  /** 발화 조건은 미정이라 표시 여부만 받는다 */
  hasSettingsNotification?: boolean;
  onSettingsClick?: () => void;
  onProfileClick?: () => void;
  /** 전달 시 프로필 버튼이 이 내용을 여는 트리거가 된다. 메뉴 항목은 소비처가 안다 */
  profileMenu?: React.ReactNode;
  className?: string;
}

/**
 * 닫힌 SNB 하단. 설정과 프로필이 세로로 붙는다.
 * 펼침에서는 설정이 프로필 행 안에 들어가므로 두 형상을 합치지 않았다.
 */
export default function SnbRailFooter({
  userName,
  hasSettingsNotification = false,
  onSettingsClick,
  onProfileClick,
  profileMenu,
  className,
}: SnbRailFooterProps) {
  const profileButton = (
    <button
      type="button"
      aria-label={userName}
      onClick={onProfileClick}
      className="flex size-9 cursor-pointer items-center justify-center"
    >
      <IconProfile aria-hidden className="border-line-normal-assistive size-9 rounded-xl border" />
    </button>
  );

  return (
    <div className={cn('flex flex-col items-center gap-4', className)}>
      <button
        type="button"
        aria-label="설정"
        onClick={onSettingsClick}
        className="hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed relative flex size-9 cursor-pointer items-center justify-center rounded-xl transition-colors"
      >
        <IconSettings aria-hidden className="text-icon-normal-neutral size-6" />
        {hasSettingsNotification && (
          <span
            data-testid="snb-rail-settings-dot"
            className="bg-icon-primary-assistive absolute top-1 right-1 size-1.5 rounded-full"
          />
        )}
      </button>
      {profileMenu ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>{profileButton}</DropdownMenuTrigger>
          {profileMenu}
        </DropdownMenu>
      ) : (
        profileButton
      )}
    </div>
  );
}
