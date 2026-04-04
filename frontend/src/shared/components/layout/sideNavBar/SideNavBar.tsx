'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';

import Close from '@/public/icons/icon/close.svg';
import Open from '@/public/icons/icon/open.svg';
import CatchupLogo from '@/public/icons/logo/logo_catchup.svg';
import CatchupLogoLetter from '@/public/icons/logo/logo_catchup_letter.svg';
import SideNavMenu from '@/shared/components/layout/sideNavBar/SideNavMenu';
import SideNavQuestions from '@/shared/components/layout/sideNavBar/SideNavQuestions';
import SideNavUser from '@/shared/components/layout/sideNavBar/SideNavUser';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { cn } from '@/shared/utils/cn';

export default function SideNavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const isRagAnswerPage = pathname.startsWith('/chat');
  const { isSidebarOpen, setSidebarOpen } = useSidebarStore();

  // isRagAnswerPage 변경 시 사이드바 상태 동기화
  useEffect(() => {
    setSidebarOpen(!isRagAnswerPage);
  }, [isRagAnswerPage, setSidebarOpen]);

  const isOpen = isSidebarOpen;

  return (
    <>
      <nav
        className={cn(
          'border-edge-neutral bg-fill-normal flex h-screen flex-col gap-5 border-r',
          'transition-[width,padding] duration-300 ease-out will-change-[width,padding]',
          isOpen ? 'w-60.25 px-2 py-2.5' : 'w-18 items-center px-3 pt-2.5 pb-5',
        )}
      >
        {/* 로고/열림 버튼 */}
        <div className={cn('flex', isOpen ? 'items-center justify-between' : '')}>
          <div
            onClick={() => router.push('/')}
            className={cn('flex cursor-pointer items-center gap-2.5', isOpen ? 'px-1' : '')}
          >
            <div
              className={cn(
                'group relative flex h-10 w-10 items-center px-1.25 py-1.5',
                isOpen ? '' : 'border-edge-neutral rounded-xl border-[0.5px]',
              )}
            >
              <CatchupLogo className="relative left-px h-7.5 w-7" />

              {!isOpen && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setSidebarOpen(true);
                      }}
                      className="bg-fill-interaction-hover active:bg-fill-interaction-pressed border-edge-strong absolute inset-0 cursor-pointer rounded-xl border-[0.5px] p-1.5 opacity-0 transition-opacity group-hover:opacity-100"
                    >
                      <Open className="h-6 w-6" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right">사이드바 열기</TooltipContent>
                </Tooltip>
              )}
            </div>

            {isOpen && (
              <div
                className={cn(
                  'relative top-0.5 flex items-center',
                  'transition-all duration-200 ease-out',
                  isOpen ? 'translate-x-0 opacity-100' : 'pointer-events-none -translate-x-2 opacity-0',
                )}
              >
                <CatchupLogoLetter className="h-5 w-auto" />
              </div>
            )}
          </div>
          {isOpen && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => setSidebarOpen(false)}
                  className="icon-button-only-gray flex cursor-pointer items-center justify-center rounded-full! p-0.5"
                >
                  <Close className="text-icon-neutral h-6 w-6" />
                </button>
              </TooltipTrigger>
              <TooltipContent>사이드바 닫기</TooltipContent>
            </Tooltip>
          )}
        </div>

        <SideNavMenu isOpen={isOpen} />
        {isOpen && <SideNavQuestions />}
        <SideNavUser isOpen={isOpen} />
      </nav>
    </>
  );
}
