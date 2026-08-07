import CatchupLogo from '@/public/icons/logo/logo_catchup.svg';
import { cn } from '@/shared/utils/cn';

export interface SideNavRailProps {
  /** Divider 위에 고정되는 모드 스위처 */
  spaceSwitcher: React.ReactNode;
  /** Divider 아래 아이템 목록. 구성은 아직 결정되지 않아 소비처가 넣는다 */
  children: React.ReactNode;
  footer: React.ReactNode;
  onExpand: () => void;
  className?: string;
}

/**
 * 접힌 전역 SNB의 셸.
 *
 * 펼침과 구조가 아예 다르다 — 브랜드 헤더 대신 로고 버튼 하나, 섹션 대신 평면 목록,
 * 설정이 하단에 독립으로 놓인다. 그래서 하나의 컴포넌트에 열림 분기를 두지 않았다.
 */
export default function SideNavRail({ spaceSwitcher, children, footer, onExpand, className }: SideNavRailProps) {
  return (
    <nav
      className={cn(
        'border-line-normal-neutral bg-fill-normal-normal flex h-full w-16 flex-col items-center border-r px-2 pt-2.5 pb-4',
        className,
      )}
    >
      <button
        type="button"
        aria-label="사이드바 펼치기"
        onClick={onExpand}
        className="hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed flex size-9 cursor-pointer items-center justify-center rounded-xl transition-colors"
      >
        <CatchupLogo aria-hidden className="h-7.5 w-7" />
      </button>

      <div className="mt-3 flex flex-col items-center gap-1">{spaceSwitcher}</div>

      {/* 스위처와 20, 목록과 12 — 위아래 간격이 다르다 */}
      <div
        aria-hidden
        data-slot="side-nav-rail-divider"
        className="bg-line-normal-neutral mt-5 mb-3 h-px w-5 shrink-0"
      />

      <div className="flex w-full flex-col items-center gap-2.5">{children}</div>

      <div className="mt-auto">{footer}</div>
    </nav>
  );
}
