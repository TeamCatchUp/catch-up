'use client';

import clsx from 'clsx';
import { useState, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useUserStore } from '@/store/userStore';
import CatchupLogo from '/public/icons/logo/logo_catchup.svg';
import CatchupLogoLetter from '/public/icons/logo/logo_catchup_letter.svg';
import Close from '/public/icons/icon/close.svg';
import Open from '/public/icons/icon/open.svg';
import TeamSpace from '/public/icons/icon/teamspace.svg';
import Dropdown from '/public/icons/icon/dropdown_down.svg';
import Kebeb from '/public/icons/icon/kebeb 2.svg';
import Home from '/public/icons/icon/home.svg';
import AI from '/public/icons/icon/ai.svg';
import Dashboard from '/public/icons/icon/dashboard.svg';
import Mail from '/public/icons/icon/inbox.svg';
import Profile from '/public/icons/icon/profile.svg';
import UnfoldMore from '/public/icons/icon/unfold_more.svg';
import ArrowLeft from '/public/icons/icon/arrow_left.svg';
import ArrowRight from '/public/icons/icon/arrow_right.svg';
import Necessary from '/public/icons/icon/necessary.svg';
import ToolTip from '@/components/common/ToolTip';
import TeamSpaceMoreModal from '@/components/common/sideNavBar/modal/TeamSpaceMoreModal';
import TeamSpaceDropDownModal from '@/components/common/sideNavBar/modal/TeamSpaceDropDownModal';
import UserModal from '@/components/common/sideNavBar/modal/UserModal';
import CatchAssistantModal from '@/components/rag/modal/CatchAssistantModal';
import api from '@/api/axios';
import { searchService } from '@/api/search';
import Link from 'next/link';

interface ChatRoomQuery {
  title: string;
  sessionId: string;
}

const TEAM_SPACES = [
  { id: 'fe', name: 'Catch Up | FE' },
  { id: 'be', name: 'Catch Up | BE' },
  { id: 'pm', name: 'Catch Up | 기획' },
  { id: 'design', name: 'Catch Up | Design' },
] as const;

const navItems = [
  { name: '홈', href: '/', Icon: Home, tooltipOpen: '최근 업무 보기', tooltipClosed: '홈' },
  {
    name: '캐치스턴트 AI',
    href: '/search',
    Icon: AI,
    tooltipOpen: '사내 지식 물어보기',
    tooltipClosed: '캐치스턴트 AI',
  },
  // {
  //   name: '업무 대시보드',
  //   href: '/stacks',
  //   Icon: Dashboard,
  //   tooltipOpen: '나의 업무 이력 확인하기',
  //   tooltipClosed: '내 업무 관리',
  // },
  // { name: '수신함', href: '/mail', Icon: Mail, tooltipOpen: '멘션 및 알림 보기', tooltipClosed: '수신함' },
];

const SideNavBar = () => {
  const pathname = usePathname();
  const router = useRouter();
  const isRagAnswerPage = pathname.startsWith('/ragAnswer');
  const [isOpen, setIsOpen] = useState(() => !isRagAnswerPage); // SNB opened 여부
  const [isTeamSpaceMoreModalOpen, setIsTeamSpaceMoreModalOpen] = useState(false); // 팀스페이스 더보기 버튼 모달 opened 여부
  const [isTeamDropDownModalOpen, setIsTeamDropDownModalOpen] = useState(false); // 팀스페이스 드롭다운 버튼 모달 opened 여부
  const [isUserModalOpen, setIsUserModalOpen] = useState(false); // 유저 모달 opened 여부
  const [isCatchModalOpen, setIsCatchModalOpen] = useState(false); // 캐치스턴트 모달 opened 여부

  const [recentChatrooms, setRecentChatrooms] = useState<ChatRoomQuery[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const user = useUserStore((state) => state.user);

  const [selectedTeamSpaceId, setSelectedTeamSpaceId] = useState<string>(TEAM_SPACES[0].id);
  const selectedTeamSpace = TEAM_SPACES.find((t) => t.id === selectedTeamSpaceId) ?? TEAM_SPACES[0];

  useEffect(() => {
    setIsOpen(!isRagAnswerPage);
  }, [isRagAnswerPage]);

  useEffect(() => {
    const fetchDefaultData = async () => {
      try {
        setIsLoading(true);
        const [chatroomRes] = await Promise.all([searchService.getRecentChatromms()]);
        if (chatroomRes.content) {
          const mappedChatrooms = chatroomRes.content.map((item: any) => ({
            title: item.title,
            sessionId: item.sessionId,
          }));
          setRecentChatrooms(mappedChatrooms);
        }
      } catch (err) {
        console.error('데이터 로드 실패:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchDefaultData();
  }, []);

  // SNB item (메뉴 상태별 스타일 CSS)
  const defaultClass =
    'border-transparent bg-white hover:bg-neutral-2 hover:border-neutral-2 active:bg-neutral-3 active:border active:border-neutral-3'; // hover, active
  const selectedClass = 'border-neutral-2 border bg-blue-1 hover:border-neutral-2 hover:bg-blue-5';

  return (
    <>
      <nav
        className={clsx(
          'border-neutral-3 flex h-screen flex-col gap-5 border-r bg-white',
          isOpen ? 'w-60.25 px-2 py-2.5' : 'w-18 items-center px-3 py-5',
        )}
      >
        {/* 로고/열림 버튼 */}
        <div className={clsx('flex', isOpen ? 'items-center justify-between' : '')}>
          <div
            onClick={() => router.push('/')}
            className={clsx('flex cursor-pointer items-center gap-2.5', isOpen ? 'px-1' : '')}
          >
            <div
              className={clsx(
                'group relative flex h-10 w-10 items-center px-1.25 py-1.5',
                isOpen ? '' : 'border-neutral-3 rounded-xl border-[0.5px]',
              )}
            >
              <CatchupLogo className="relative left-px h-7.5 w-7" />

              {!isOpen && (
                <div className="group flex gap-px">
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      setIsOpen(true);
                    }}
                    className="transition:opacity bg-neutral-2 active:bg-neutral-3 border-neutral-5 absolute inset-0 cursor-pointer rounded-xl border-[0.5px] p-1.5 opacity-0 group-hover:opacity-100"
                  >
                    <Open className="h-6 w-6" />
                  </button>
                  <div className="relative bottom-4.5 left-2">
                    <ToolTip text={'사이드바 열기'} />
                  </div>
                </div>
              )}
            </div>

            {isOpen && (
              <div className="relative top-0.5 flex items-center">
                <CatchupLogoLetter />
              </div>
            )}
          </div>
          {isOpen && (
            <div className="group flex gap-px">
              <button className="icon-button-only-gray flex items-center justify-center rounded-full! p-0.5">
                <Close onClick={() => setIsOpen(false)} className="h-6 w-6 cursor-pointer text-gray-50" />
              </button>
              <div className="relative bottom-1 left-0.5">
                <ToolTip text={'사이드바 닫기'} />
              </div>
            </div>
          )}
        </div>

        {/* 팀스페이스 */}
        {isOpen && (
          <div
            onClick={() => {
              setIsTeamSpaceMoreModalOpen(false);
              setIsTeamDropDownModalOpen((prev) => !prev);
            }}
            onMouseEnter={() => {
              setIsTeamSpaceMoreModalOpen(false);
              setIsTeamDropDownModalOpen(true);
            }}
            onMouseLeave={() => {
              setIsTeamDropDownModalOpen(false);
            }}
            className={clsx(
              'group/teamspace border-neutral-3 flex cursor-pointer flex-col justify-center gap-1.5 rounded-xl! border px-2.5 py-2',
              isTeamSpaceMoreModalOpen || isTeamDropDownModalOpen ? 'bg-neutral-2' : 'hover:bg-neutral-2 bg-white',
            )}
          >
            <span className="flex items-center justify-between">
              <span className="text-body-xsmall text-gray-50">팀스페이스</span>
              <Dropdown
                onClick={(e: React.MouseEvent<SVGSVGElement>) => {
                  e.stopPropagation();
                  setIsTeamSpaceMoreModalOpen(false);
                  setIsTeamDropDownModalOpen(!isTeamDropDownModalOpen);
                }}
                className={clsx(
                  'h-4 w-4 cursor-pointer rounded-full text-gray-50 transition-opacity',
                  isTeamDropDownModalOpen
                    ? 'bg-neutral-3 opacity-100'
                    : 'hover:bg-neutral-3 active:bg-neutral-4 opacity-0 group-hover/teamspace:opacity-100',
                )}
              />
            </span>
            <div className="flex">
              <div className="flex items-center">
                <div className="bg-neutral-3 h-6 w-6 rounded-md">
                  <TeamSpace className="text-gray-70" />
                </div>
                <div className="relative right-1.25 bottom-2.75">
                  <Necessary className="h-2 w-2" />
                </div>
              </div>

              <div className="relative min-w-0 flex-1">
                <div
                  className={clsx(
                    isTeamSpaceMoreModalOpen
                      ? 'text-body-small text-gray-80 relative top-px left-1 max-w-36 truncate'
                      : 'text-body-small text-gray-80 relative top-px left-1 max-w-42 truncate group-hover/teamspace:max-w-36',
                  )}
                >
                  {selectedTeamSpace.name}
                </div>
                <div className="group absolute top-0 right-0">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setIsTeamSpaceMoreModalOpen(!isTeamSpaceMoreModalOpen);
                      setIsTeamDropDownModalOpen(false);
                    }}
                    className={clsx(
                      'ml-3 flex h-5.5 w-5.5 cursor-pointer items-center justify-center rounded-full p-0.5 transition-opacity',
                      isTeamSpaceMoreModalOpen
                        ? 'bg-neutral-3 opacity-100'
                        : 'hover:bg-neutral-3 active:bg-neutral-4 opacity-0 group-hover/teamspace:opacity-100',
                    )}
                  >
                    <Kebeb className="h-4.5 w-4.5 text-gray-50" />
                  </button>
                  <div className="relative bottom-6.75 left-9">
                    <ToolTip text={'팀원 추가 및 설정'} />
                  </div>
                </div>
              </div>
            </div>
            {/* 팀스페이스 모달 */}
            {isTeamSpaceMoreModalOpen && (
              <div className="absolute top-32 left-49 z-100">
                <TeamSpaceMoreModal onClose={() => setIsTeamSpaceMoreModalOpen(false)} />
              </div>
            )}
            {isTeamDropDownModalOpen && (
              <div className="absolute top-17.5 left-58.5 z-100">
                <TeamSpaceDropDownModal
                  onClose={() => setIsTeamDropDownModalOpen(false)}
                  teamSpaces={[...TEAM_SPACES]}
                  selectedId={selectedTeamSpaceId}
                  onSelect={(team) => {
                    setSelectedTeamSpaceId(team.id);
                  }}
                />
              </div>
            )}
          </div>
        )}
        {!isOpen && (
          <div
            onClick={() => {
              setIsTeamSpaceMoreModalOpen(false);
              setIsTeamDropDownModalOpen((prev) => !prev);
            }}
            onMouseEnter={() => {
              setIsTeamSpaceMoreModalOpen(false);
              setIsTeamDropDownModalOpen(true);
            }}
            onMouseLeave={() => {
              setIsTeamDropDownModalOpen(false);
            }}
            className={clsx(
              'group border-neutral-3 shadow-blue-bottom flex h-10 w-14.5 cursor-pointer items-center justify-center rounded-xl border p-1.5',
              isTeamDropDownModalOpen ? 'bg-neutral-2' : 'hover:bg-neutral-2 bg-white',
            )}
          >
            <div className="flex items-center gap-1.5">
              <div className="relative flex">
                <div
                  className={clsx(
                    'text-body-small rounded-md2 flex h-6 w-6 items-center justify-center text-gray-50',
                    isTeamDropDownModalOpen ? 'bg-neutral-3' : 'bg-neutral-2 group-hover:bg-neutral-3',
                  )}
                >
                  {selectedTeamSpace.name.trim().charAt(0)}
                </div>
                <div className="absolute bottom-4.75 left-4.5">
                  <Necessary className="h-2 w-2" />
                </div>
              </div>
              <div
                onClick={(e) => {
                  e.stopPropagation();
                  setIsTeamDropDownModalOpen(!isTeamDropDownModalOpen);
                }}
                className="h-4 w-4"
              >
                <Dropdown className="text-gray-50" />
              </div>
            </div>
            {isTeamDropDownModalOpen && (
              <div className="absolute top-20 left-17 z-100">
                <TeamSpaceDropDownModal
                  onClose={() => setIsTeamDropDownModalOpen(false)}
                  teamSpaces={[...TEAM_SPACES]}
                  selectedId={selectedTeamSpaceId}
                  onSelect={(team) => {
                    setSelectedTeamSpaceId(team.id);
                  }}
                />
              </div>
            )}
          </div>
        )}

        {/* 메뉴 */}
        <div className={`flex flex-col ${isOpen ? 'gap-1' : 'gap-2'}`}>
          {navItems.map((item) => {
            const isActive = pathname === item.href;

            const handleClick = () => {
              if (item.href === '/search') {
                const newSessionId = crypto.randomUUID();
                // router.push(`/ragAnswer/${newSessionId}`);
                router.push(`/search`);
              } else {
                router.push(item.href);
              }
            };

            return (
              <div key={item.name} className="group relative">
                <button
                  onClick={handleClick}
                  className={clsx(
                    'flex h-10 cursor-pointer items-center rounded-lg',
                    isActive ? selectedClass : defaultClass,
                    isOpen ? 'w-56.5 gap-3 px-2.5 py-2' : 'w-10 items-center justify-center',
                  )}
                >
                  <item.Icon
                    className={clsx(
                      isOpen ? 'h-5.5 w-5.5' : 'h-7 w-7',
                      isActive ? 'text-blue-50 group-hover:text-blue-50' : 'text-gray-70',
                    )}
                  />
                  {isOpen && (
                    <span
                      className={clsx(
                        'text-body-small relative',
                        isActive ? 'text-blue-55 group-hover:text-blue-55' : 'text-gray-80',
                      )}
                    >
                      {item.name}
                    </span>
                  )}
                  {isOpen && item.name === '수신함' && (
                    <div className="rounded-md2 bg-blue-1 border-blue-30 ml-auto flex h-5.75 w-5.75 items-center justify-center border-[0.5px] px-0.5">
                      <span className="text-body-small text-blue-40">2</span>
                    </div>
                  )}
                </button>
                <div className="flex opacity-0 transition-opacity group-hover:opacity-100">
                  {isOpen ? (
                    <div className={clsx('relative bottom-9.5 left-57')}>
                      <ToolTip text={item.tooltipOpen} />
                    </div>
                  ) : (
                    <div className="relative bottom-9.25 left-10.5">
                      <ToolTip text={item.tooltipClosed} />
                    </div>
                  )}
                </div>
                {!isOpen && item.name === '수신함' && (
                  <div className="relative bottom-9 left-7.5">
                    <Necessary className="h-2 w-2" />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* 질문 목록 */}
        {isOpen && (
          <div className="flex min-h-0 flex-1 flex-col">
            <button onClick={() => setIsCatchModalOpen(true)} className="h-7 w-fit cursor-pointer items-center">
              {!isCatchModalOpen ? (
                <div className="text-button-secondary-mono flex px-2.5 py-1">
                  <span className="text-body-xsmall text-gray-70">내 질문</span>
                  <ArrowRight className="h-5 w-5 text-gray-50" />
                </div>
              ) : (
                <span className="bg-neutral-4 flex items-center gap-1 rounded-full px-1.5 py-1">
                  <ArrowLeft className="text-gray-70 h-5 w-5" />
                  <span className="text-body-xsmall text-gray-70 relative top-px">더보기</span>
                  <ArrowRight className="text-gray-70 h-5 w-5" />
                </span>
              )}
            </button>
            <div className="mt-2 flex flex-col overflow-y-auto">
              {recentChatrooms.map((chatroom) => {
                return (
                  <Link
                    href={`/ragAnswer/${chatroom.sessionId}`}
                    key={chatroom.sessionId}
                    // , isActive ? selectedClass : defaultClass
                    className={clsx('group flex cursor-pointer rounded-lg py-2')}
                  >
                    {/* , isActive ? 'text-blue-55' : 'text-gray-80' */}
                    <span className={clsx('text-body-small truncate px-2.5')}>{chatroom.title}</span>
                    <span className="mr-2.5 ml-auto flex h-5 w-5 items-center opacity-0 transition-opacity group-hover:opacity-100">
                      <Kebeb className="text-gray-50" />
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        )}

        {/* 유저 */}
        <div className={'group mt-auto flex flex-col gap-1.5'}>
          {isOpen && <div className={`bg-neutral-3 relative right-2 h-px w-60`} />}
          <div
            onClick={() => setIsUserModalOpen(!isUserModalOpen)}
            className={clsx(
              'flex h-13.5 cursor-pointer items-center rounded-lg',
              isOpen ? 'icon-button-only-gray w-56.25 justify-between px-1.5 py-1' : 'justify-center',
            )}
          >
            <div className={clsx('flex gap-4', isOpen ? 'mt-auto' : '')}>
              <Profile className="border-neutral-2 h-10 w-10 rounded-xl border-[0.5px]" />
              {isOpen && (
                <div className="relative top-px max-w-31">
                  <div className="text-heading-small text-gray-80 truncate">{user?.name ?? '이름없음'}</div>
                  <div className="text-body-small truncate text-gray-50">{user?.email ?? ''}</div>
                </div>
              )}
            </div>
            {isOpen && (
              <div className="bottom-1 flex cursor-pointer items-center p-0.5">
                <UnfoldMore className="h-6 w-6" />
              </div>
            )}
          </div>
          {!isOpen && (
            <div className="relative bottom-15.5 left-10.5">
              <ToolTip
                text={
                  <div className="flex flex-col">
                    <span>{user?.name ?? '이름없음'}</span>
                    <span>{user?.email ?? '역할없음'}</span>
                  </div>
                }
              />
            </div>
          )}
          {isUserModalOpen && (
            <div className="absolute bottom-15.5 z-100">
              <UserModal onClose={() => setIsUserModalOpen(false)} userName={user?.name} userEmail={user?.email} />
            </div>
          )}
        </div>
      </nav>
      {/* {isCatchModalOpen && <CatchAssistantModal onClose={() => setIsCatchModalOpen(false)} />} */}
      {isCatchModalOpen && (
        <div className="fixed inset-0 z-100 flex items-center justify-center">
          {/* 배경 오버레이 */}
          <div className="absolute inset-0 bg-white/50" onClick={() => setIsCatchModalOpen(false)} />

          {/* 모달 */}
          <div className="relative z-10">
            <CatchAssistantModal onClose={() => setIsCatchModalOpen(false)} />
          </div>
        </div>
      )}
    </>
  );
};

export default SideNavBar;
