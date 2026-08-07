import IconClose from '@/public/icons/icon/close.svg';
import CatchupLogo from '@/public/icons/logo/logo_catchup.svg';
import CatchupLogoLetter from '@/public/icons/logo/logo_catchup_letter.svg';
import { cn } from '@/shared/utils/cn';

export interface SideNavShellProps {
  /** 주 메뉴 위에 고정되는 모드 스위처 */
  spaceSwitcher: React.ReactNode;
  /**
   * 모드 스위처 아래 주 내비 블록들. 자식 하나하나가 12 간격으로 놓인다 —
   * 위키는 메뉴 행 묶음 / 팀스페이스 카드 / 드롭다운 행 묶음 세 덩어리를 넘긴다.
   * 행끼리 붙여야 하는 묶음은 소비처가 감싸서 넘긴다.
   */
  primaryItems: React.ReactNode;
  /** 그 아래 섹션들. 구성은 모드마다 다르고 아직 확정되지 않아 소비처가 조립한다 */
  children: React.ReactNode;
  footer: React.ReactNode;
  onCollapse: () => void;
  showScrollFade?: boolean;
  className?: string;
}

/**
 * 펼친 전역 SNB의 셸.
 *
 * 섹션 구성을 slot으로 받는 이유는 홈과 LLM Wiki의 구성이 다르고, 그 구성 자체가
 * 아직 결정되지 않았기 때문이다. 셸이 목록을 알면 미결을 코드가 정해 버린다.
 *
 * 빈 목록을 받아도 대체 문구를 만들지 않는다 — 빈 상태 카피는 승인된 시안이 없다.
 */
export default function SideNavShell({
  spaceSwitcher,
  primaryItems,
  children,
  footer,
  onCollapse,
  showScrollFade = false,
  className,
}: SideNavShellProps) {
  return (
    <nav
      className={cn(
        'border-line-normal-neutral bg-fill-normal-normal flex h-full w-60 flex-col border-r pb-3',
        className,
      )}
    >
      <div className="flex min-h-0 flex-1 flex-col gap-0.5">
        <div className="flex items-center justify-between p-2">
          <span className="flex items-center gap-1.5">
            <span className="flex size-10 items-center justify-center rounded-xl">
              <CatchupLogo aria-hidden className="h-7.5 w-7" />
            </span>
            <CatchupLogoLetter aria-hidden className="h-5 w-auto" />
          </span>
          <button
            type="button"
            aria-label="사이드바 접기"
            onClick={onCollapse}
            className="hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed flex size-9 cursor-pointer items-center justify-center rounded-lg transition-colors"
          >
            <IconClose aria-hidden className="text-icon-normal-normal size-6" />
          </button>
        </div>

        <div
          data-testid="side-nav-shell-nav-area"
          className="custom-scrollbar flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-2"
        >
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-1.5">{spaceSwitcher}</div>
            {primaryItems}
          </div>
          {children}
        </div>

        {showScrollFade && (
          <div className="to-fill-normal-normal pointer-events-none -mt-12.5 h-12.5 shrink-0 bg-linear-to-b from-transparent" />
        )}
      </div>

      {footer}
    </nav>
  );
}
