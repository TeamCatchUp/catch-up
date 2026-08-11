import IconAdd from '@/public/icons/icon/add_small.svg';
import IconProfile from '@/public/icons/icon/profile.svg';
import IconSettings from '@/public/icons/icon/settings.svg';
import { cn } from '@/shared/utils/cn';

export interface SnbFooterProps {
  userName: string;
  /** 직책. 서버 값이 없으면 소비처가 빈 문자열을 준다 — 대체 문구를 이 컴포넌트가 만들지 않는다 */
  userRole: string;
  onNewClick?: () => void;
  onProfileClick?: () => void;
  onSettingsClick?: () => void;
  className?: string;
}

/**
 * 펼친 SNB 하단. 신규 버튼과 프로필 행을 담고, 설정 진입점이 프로필 행 안에 있다.
 * 닫힘에서는 형상이 달라 한 컴포넌트로 합치지 않았다.
 */
export default function SnbFooter({
  userName,
  userRole,
  onNewClick,
  onProfileClick,
  onSettingsClick,
  className,
}: SnbFooterProps) {
  return (
    <div className={cn('border-line-normal-neutral flex flex-col gap-1 border-t px-2 pt-2.5', className)}>
      <div className="flex items-center justify-center px-1">
        <button
          type="button"
          onClick={onNewClick}
          className="border-line-normal-normal bg-fill-normal-normal hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed flex h-9 w-full cursor-pointer items-center justify-center gap-1.5 rounded-full border px-3 py-1.5 transition-colors"
        >
          <IconAdd aria-hidden className="text-icon-normal-normal size-5 shrink-0" />
          <span className="text-body-small text-text-normal-normal">신규</span>
        </button>
      </div>

      <div className="hover:bg-fill-normal-interaction-hover flex items-center gap-3 rounded-lg px-2.5 py-0.5 transition-colors">
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
        <button
          type="button"
          aria-label="설정"
          onClick={onSettingsClick}
          className="border-line-normal-neutral bg-fill-normal-normal hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed flex size-7.5 shrink-0 cursor-pointer items-center justify-center rounded-md border transition-colors"
        >
          <IconSettings aria-hidden className="text-icon-normal-normal size-5" />
        </button>
      </div>
    </div>
  );
}
