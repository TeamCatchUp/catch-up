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
import { Button } from '@/shared/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { cn } from '@/shared/utils/cn';

export default function SideNavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const isRagAnswerPage = pathname.startsWith('/chat');
  const isSettingsRoute = pathname.startsWith('/mypage') || pathname.startsWith('/admin');
  const { isSidebarOpen, setSidebarOpen } = useSidebarStore();

  // 채팅·설정 페이지 진입 시 사이드바 자동 닫힘
  useEffect(() => {
    setSidebarOpen(!isRagAnswerPage && !isSettingsRoute);
  }, [isRagAnswerPage, isSettingsRoute, setSidebarOpen]);

  const isOpen = isSidebarOpen;

  return (
    <>
      <nav
        className={cn(
          'border-edge-neutral bg-background-normal-normal flex h-screen flex-col border-r',
          'transition-[width,padding] duration-300 ease-out will-change-[width,padding]',
          isOpen ? 'w-60.25 px-2 pb-2.5' : 'w-13 items-center gap-4 px-2 pt-2.5 pb-4',
        )}
      >
        {/* 로고/열림 버튼 */}
        <div className={cn('flex', isOpen ? 'mb-1.5 items-center justify-between py-2.5' : '')}>
          <div
            onClick={() => router.push('/')}
            className={cn('flex cursor-pointer items-center gap-2.5', isOpen ? 'px-1' : '')}
          >
            <Tooltip>
              <TooltipTrigger asChild>
                <div
                  className={cn(
                    'group relative flex h-9 w-9 items-center px-1.25 py-1.5',
                    isOpen
                      ? ''
                      : isSettingsRoute
                        ? 'hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed rounded-xl'
                        : 'border-edge-neutral rounded-xl border',
                  )}
                  onClick={
                    !isOpen && isSettingsRoute
                      ? (e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          router.push('/');
                        }
                      : undefined
                  }
                >
                  <CatchupLogo className="relative left-px h-7.5 w-7" />

                  {!isOpen && !isSettingsRoute && (
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setSidebarOpen(true);
                      }}
                      className="bg-fill-interaction-hover active:bg-fill-interaction-pressed border-edge-strong absolute inset-0 cursor-pointer rounded-xl border p-1.5 opacity-0 transition-opacity group-hover:opacity-100"
                    >
                      <Open className="h-6 w-6" />
                    </button>
                  )}
                </div>
              </TooltipTrigger>
              {!isOpen && <TooltipContent side="right">{isSettingsRoute ? '홈으로' : '사이드바 열기'}</TooltipContent>}
            </Tooltip>

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
                <Button
                  variant="icon-only-gray"
                  size="md"
                  onClick={() => setSidebarOpen(false)}
                  aria-label="사이드바 닫기"
                >
                  <Close className="h-6 w-6" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>사이드바 닫기</TooltipContent>
            </Tooltip>
          )}
        </div>

        {isOpen ? (
          <>
            <div className="flex min-h-0 flex-1 flex-col gap-5">
              <SideNavMenu isOpen={isOpen} />
              <SideNavQuestions />
            </div>
            <SideNavUser isOpen={isOpen} />
          </>
        ) : (
          <>
            <SideNavMenu isOpen={isOpen} />
            <SideNavUser isOpen={isOpen} />
          </>
        )}
      </nav>
    </>
  );
}
