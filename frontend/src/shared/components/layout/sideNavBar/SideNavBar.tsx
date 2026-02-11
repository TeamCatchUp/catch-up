'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import RecentQuestionsModal from '@/shared/components/layout/sideNavBar/modal/RecentQuestionsModal';
import { UserMenuContent } from '@/shared/components/layout/sideNavBar/modal/UserModal';
import { DropdownMenu, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';
import { Tooltip, TooltipContent,TooltipTrigger } from '@/shared/components/ui/ToolTip';
import { chatQueries } from '@/shared/queries/chatroom.queries';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { useUserStore } from '@/shared/store/userStore';
import { cn } from '@/shared/utils/cn';

import AI from '/public/icons/icon/ai.svg';
import ArrowRight from '/public/icons/icon/arrow_right.svg';
import Close from '/public/icons/icon/close.svg';
import Home from '/public/icons/icon/home.svg';
import Inbox from '/public/icons/icon/inbox.svg';
import Kebeb from '/public/icons/icon/kebeb 2.svg';
import Open from '/public/icons/icon/open.svg';
import Profile from '/public/icons/icon/profile.svg';
import Settings from '/public/icons/icon/settings.svg';
import UnfoldMore from '/public/icons/icon/unfold_more.svg';
import CatchupLogo from '/public/icons/logo/logo_catchup.svg';
import CatchupLogoLetter from '/public/icons/logo/logo_catchup_letter.svg';

interface ChatRoomQuery {
  title: string;
  session_id: string;
}

const UNREAD_COUNT = 3; // mock

const navItems = [
  { name: '홈', href: '/', Icon: Home, tooltipOpen: '최근 업무 보기', tooltipClosed: '홈' },
  { name: '캐치스턴트 AI', href: '/search', Icon: AI, tooltipOpen: '사내 지식 물어보기', tooltipClosed: '캐치스턴트 AI' },
  { name: '수신함', panel: 'inbox' as const, Icon: Inbox, tooltipOpen: '수신함', tooltipClosed: '수신함' },
  { name: '설정', panel: 'settings' as const, Icon: Settings, tooltipOpen: '설정', tooltipClosed: '설정' },
];

const SideNavBar = () => {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { activePanel, togglePanel, setActivePanel } = useSidebarStore();
  const isRagAnswerPage = pathname.startsWith('/chat');
  const [isOpen, setIsOpen] = useState(() => !isRagAnswerPage);
  const [isCatchModalOpen, setIsCatchModalOpen] = useState(false);

  const { data: chatroomData } = useQuery(chatQueries.recentRooms());

  const recentChatrooms = useMemo<ChatRoomQuery[]>(() => {
    if (!chatroomData?.content) return [];
    return chatroomData.content
      .map((item) => ({
        title: item.title,
        session_id: item.session_id,
      }))
      .reverse();
  }, [chatroomData]);

  const user = useUserStore((state) => state.user);

  // isRagAnswerPage 변경 시 사이드바 상태 동기화 (adjusting state during render)
  const [prevIsRagAnswerPage, setPrevIsRagAnswerPage] = useState(isRagAnswerPage);
  if (prevIsRagAnswerPage !== isRagAnswerPage) {
    setPrevIsRagAnswerPage(isRagAnswerPage);
    setIsOpen(!isRagAnswerPage);
  }

  // refresh_sidebar 이벤트 → TanStack Query invalidation
  useEffect(() => {
    const handleRefresh = () => {
      queryClient.invalidateQueries({ queryKey: chatQueries.all() });
    };
    window.addEventListener('refresh_sidebar', handleRefresh);
    return () => window.removeEventListener('refresh_sidebar', handleRefresh);
  }, [queryClient]);

  // SNB item (메뉴 상태별 스타일 CSS)
  const defaultClass =
    'bg-white hover:bg-neutral-2 active:bg-neutral-3 active:ring-1 active:ring-neutral-3';
  const selectedClass = 'ring-1 ring-neutral-2 bg-blue-1 hover:bg-blue-5';

  return (
    <>
      <nav
        className={cn(
          'border-neutral-3 flex h-screen flex-col gap-5 border-r bg-white',
          'transition-[width,padding] duration-300 ease-out will-change-[width,padding]',
          isOpen ? 'w-60.25 px-2 py-2.5' : 'w-18 items-center px-3 py-5',
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
                isOpen ? '' : 'border-neutral-3 rounded-xl border-[0.5px]',
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
                        setIsOpen(true);
                      }}
                      className="bg-neutral-2 active:bg-neutral-3 border-neutral-5 absolute inset-0 cursor-pointer rounded-xl border-[0.5px] p-1.5 opacity-0 transition-opacity group-hover:opacity-100"
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
                <button onClick={() => setIsOpen(false)} className="icon-button-only-gray flex cursor-pointer items-center justify-center rounded-full! p-0.5">
                  <Close className="h-6 w-6 text-gray-50" />
                </button>
              </TooltipTrigger>
              <TooltipContent>사이드바 닫기</TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* 메뉴 */}
        <div className={`flex flex-col ${isOpen ? 'gap-1' : 'gap-2'}`}>
          {navItems.map((item) => {
            const isActive = item.href
              ? pathname === item.href
              : activePanel === item.panel;

            const handleClick = () => {
              if (item.panel) {
                if (item.panel === 'settings' && isOpen) setIsOpen(false);
                togglePanel(item.panel);
              } else {
                setActivePanel(null);
                router.push(item.href!);
              }
            };

            return (
              <div key={item.name} className="group relative">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      onClick={handleClick}
                      className={cn(
                        'relative flex h-10 cursor-pointer items-center rounded-lg',
                        isActive ? selectedClass : defaultClass,
                        isOpen ? 'w-full gap-3 px-2.5 py-2' : 'w-10 items-center justify-center',
                      )}
                    >
                      <item.Icon
                        className={cn(
                          isOpen ? 'h-6 w-6' : 'h-7 w-7',
                          isActive ? 'text-blue-50 group-hover:text-blue-50' : 'text-gray-70',
                        )}
                      />
                      {isOpen && (
                        <span
                          className={cn(
                            'text-left text-body-small relative flex-1',
                            isActive ? 'text-blue-55 group-hover:text-blue-55' : 'text-gray-80',
                          )}
                        >
                          {item.name}
                        </span>
                      )}
                      {/* 수신함 배지 (열림) */}
                      {isOpen && item.panel === 'inbox' && UNREAD_COUNT > 0 && (
                        <span className="bg-blue-1 border-blue-40 text-blue-40 text-body-small min-w-[23px] rounded-md border-[0.5px] px-0.5 text-center">
                          {UNREAD_COUNT}
                        </span>
                      )}
                      {/* 수신함 blue dot (닫힘) */}
                      {!isOpen && item.panel === 'inbox' && UNREAD_COUNT > 0 && (
                        <span className="bg-blue-40 absolute right-1 top-1.25 h-1.5 w-1.5 rounded-full" />
                      )}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    {isOpen ? item.tooltipOpen : item.tooltipClosed}
                  </TooltipContent>
                </Tooltip>
              </div>
            );
          })}
        </div>

        {/* 질문 목록 */}
        {isOpen && (
          <div className="flex min-h-0 flex-1 flex-col">
            <button onClick={() => setIsCatchModalOpen(true)} className="h-7 w-fit cursor-pointer items-center">
                <div className="text-button-secondary-mono flex items-center px-2.5 py-1">
                  <span className="text-body-xsmall text-gray-70">내 질문</span>
                  <ArrowRight className="relative bottom-px h-5 w-5 text-gray-50" />
                </div>
            </button>
            <div className="mt-2 flex flex-col overflow-y-auto">
              {recentChatrooms.map((chatroom) => {
                const isActive = pathname === `/chat/${chatroom.session_id}`;

                return (
                  <Link
                    href={`/chat/${chatroom.session_id}`}
                    key={chatroom.session_id}
                    className={cn(
                      'group flex cursor-pointer rounded-lg py-2',
                      isActive ? selectedClass : defaultClass,
                    )}
                  >
                    <span className={cn('text-body-small truncate px-2.5')}>{chatroom.title}</span>
                    <span className="mr-2.5 ml-auto flex h-5 w-5 items-center opacity-0 transition-opacity group-hover:opacity-100">
                      <Kebeb className="text-gray-50 h-4.5 w-4.5" />
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        )}

        {/* 유저 */}
        <div className="mt-auto flex flex-col gap-1.5">
          {isOpen && <div className="bg-neutral-3 relative right-2 h-px w-60" />}
          <Tooltip>
            <DropdownMenu>
              <TooltipTrigger asChild>
                <DropdownMenuTrigger asChild>
                  <button
                    className={cn(
                      'flex h-13.5 cursor-pointer items-center rounded-lg',
                      isOpen
                        ? 'w-56.25 justify-between px-1.5 py-1 hover:bg-neutral-2 data-[state=open]:bg-neutral-2'
                        : 'justify-center',
                    )}
                  >
                    <div className={cn('flex gap-4', isOpen ? 'mt-auto' : '')}>
                      <Profile className="border-neutral-2 h-10 w-10 rounded-xl border-[0.5px]" />
                      {isOpen && (
                        <div className="relative top-px max-w-31 text-left">
                          <div className="text-heading-small text-gray-80 truncate">{user?.name ?? '이름없음'}</div>
                          <div className="text-body-small truncate text-gray-50">{user?.email ?? ''}</div>
                        </div>
                      )}
                    </div>
                    {isOpen && (
                      <div className="bottom-1 flex items-center p-0.5">
                        <UnfoldMore className="h-6 w-6" />
                      </div>
                    )}
                  </button>
                </DropdownMenuTrigger>
              </TooltipTrigger>
              {!isOpen && (
                <TooltipContent side="right">
                  <div className="flex flex-col">
                    <span>{user?.name ?? '이름없음'}</span>
                    <span>{user?.email ?? '역할없음'}</span>
                  </div>
                </TooltipContent>
              )}
              <UserMenuContent userName={user?.name} userEmail={user?.email} />
            </DropdownMenu>
          </Tooltip>
        </div>
      </nav>
      {isCatchModalOpen && (
        <div className="fixed inset-0 z-100 flex items-center justify-center">
          {/* 배경 오버레이 */}
          <div className="absolute inset-0 bg-white/50" onClick={() => setIsCatchModalOpen(false)} />

          {/* 모달 */}
          <div className="relative z-10">
            <RecentQuestionsModal onClose={() => setIsCatchModalOpen(false)} />
          </div>
        </div>
      )}
    </>
  );
};

export default SideNavBar;
