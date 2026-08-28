import Link from 'next/link';

import IconClose from '@/public/icons/icon/close.svg';
import CatchupLogo from '@/public/icons/logo/logo_catchup.svg';
import CatchupLogoLetter from '@/public/icons/logo/logo_catchup_letter.svg';
import { cn } from '@/shared/utils/cn';

export interface SideNavShellProps {
  /** 주 메뉴 위에 고정되는 모드 스위처 */
  spaceSwitcher: React.ReactNode;
  /** 모드 스위처 아래 주 내비 블록들. 자식마다 간격이 붙으므로 붙여야 하는 행은 소비처가 감싸서 넘긴다. */
  primaryItems: React.ReactNode;
  /** 그 아래 섹션들. 구성이 모드마다 달라 소비처가 조립한다 */
  children: React.ReactNode;
  footer: React.ReactNode;
  onCollapse: () => void;
  showScrollFade?: boolean;
  className?: string;
}

/**
 * 펼친 전역 SNB의 셸. 섹션 구성은 모드마다 달라 slot으로 받는다.
 * 빈 목록을 받아도 대체 문구를 만들지 않는다 — 승인된 빈 상태 카피가 없다.
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
          {/* 로고는 홈 진입점이다 — 링크라 새 탭·미들클릭이 살아 있다 */}
          <Link href="/" aria-label="홈으로 이동" className="flex cursor-pointer items-center gap-1.5">
            <span className="hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed flex size-10 items-center justify-center rounded-xl transition-colors">
              <CatchupLogo aria-hidden className="h-7.5 w-7" />
            </span>
            <CatchupLogoLetter aria-hidden className="h-5 w-auto" />
          </Link>
          <button
            type="button"
            aria-label="사이드바 접기"
            onClick={onCollapse}
            className="hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed flex size-9 cursor-pointer items-center justify-center rounded-lg transition-colors"
          >
            <IconClose aria-hidden className="text-icon-normal-normal size-6" />
          </button>
        </div>

        {/* 스크롤바 자리를 늘 비워 둔다 — 목록이 넘칠 때마다 행 폭이 8px 흔들리지 않게 */}
        <div
          data-testid="side-nav-shell-nav-area"
          className="custom-scrollbar flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-2 [scrollbar-gutter:stable]"
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
