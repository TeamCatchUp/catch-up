'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import clsx from 'clsx';
import CatchupLogo from '/public/icons/logo/logo_catchup.svg';
import CatchupLogoLetter from '/public/icons/logo/logo_catchup_letter.svg';
import Close from '/public/icons/icon/close.svg';
import Open from '/public/icons/icon/open.svg';
import Home from '/public/icons/icon/home.svg';
import Search from '/public/icons/icon/edit_square.svg';
import Dashboard from '/public/icons/icon/dashboard.svg';
import Stacks from '/public/icons/icon/stacks.svg';
import Mail from '/public/icons/icon/mail.svg';
import DefaultProfile from '/public/icons/icon/default_profile.svg';
import UnfoldMore from '/public/icons/icon/unfold_more.svg';
import Kebeb from '/public/icons/icon/kebeb 2.svg';
import ArrowRight from '/public/icons/icon/arrow_right.svg';
import api from '@/api/axios';

const navItems = [
  { name: '홈', href: '/', Icon: Home },
  { name: '캐치스턴트 AI', href: '/search', Icon: Search },
  { name: '내 업무 관리하기', href: '/dashboard', Icon: Dashboard },
  { name: '인수인계 DB', href: '/stacks', Icon: Stacks },
  { name: '수신함', href: '/mail', Icon: Mail },
];

// 내 질문 목록 더미데이터
const queryItems = [
  { id: 1, content: '연동 테스트 중단 리스크' },
  { id: 2, content: 'A사 API 명세 버전 이슈' },
  { id: 3, content: 'SSO 토큰 만료 해결 여부' },
  { id: 4, content: 'A사 API 연동 오류 원인 정리' },
];

interface UserResponse {
  name: string;
  email: string;
}

const SideNavBar = () => {
  const pathname = usePathname();
  const router = useRouter();
  const isRagAnswerPage = pathname === '/ragAnswer';
  const [isOpen, setIsOpen] = useState(() => !isRagAnswerPage);
  const [user, setUser] = useState<{ name: string; email: string } | null>(null);

  useEffect(() => {
    setIsOpen(!isRagAnswerPage);
  }, [isRagAnswerPage]);

  // SNB item (메뉴 상태별 스타일 CSS)
  const defaultClass =
    'border-transparent bg-white hover:bg-neutral-2 hover:border-neutral-2 active:bg-neutral-3 active:border active:border-neutral-3'; // hover, active
  const selectedClass = 'border-neutral-2 border bg-blue-1 hover:border-neutral-2 hover:bg-blue-5';

  useEffect(() => {
    console.log('accessToken:', localStorage.getItem('accessToken'));
    const fetchUser = async () => {
      try {
        const res = await api.get('/api/me');
        console.log('me response:', res.data);
        setUser(res.data);
      } catch (err) {
        console.error('유저 정보 조회 실패: ', err);
      }
    };

    fetchUser();
  }, []);

  return (
    <nav
      className={clsx(
        'border-neutral-3 flex h-screen flex-col gap-4 border-r bg-white',
        isOpen ? 'w-60.25 px-2 py-2.5' : 'w-15.25 items-center py-5',
      )}
    >
      {/* 로고/열림 버튼 */}
      <div className={clsx('flex', isOpen ? 'items-center justify-between' : '')}>
        <div className={clsx('flex items-center gap-2.5', isOpen ? 'px-1' : '')}>
          <div className="group border-neutral-3 relative flex h-10 w-10 cursor-pointer items-center rounded-xl border-[0.5px] px-1.25 py-1.5">
            <CatchupLogo className="relative left-px h-7.5 w-7" />

            {!isOpen && (
              <button
                onClick={() => setIsOpen(true)}
                className="transition:opacity bg-neutral-2 active:bg-neutral-3 border-neutral-5 absolute inset-0 cursor-pointer rounded-xl border-[0.5px] p-1.5 opacity-0 group-hover:opacity-100"
              >
                <Open className="h-6 w-6" />
              </button>
            )}
          </div>

          {isOpen && (
            <div className="relative top-0.5 flex items-center">
              <CatchupLogoLetter />
            </div>
          )}
        </div>
        {isOpen && (
          <Close
            onClick={() => setIsOpen(false)}
            className="relative right-1 bottom-0.5 h-6 w-6 cursor-pointer p-0.5 text-gray-50"
          />
        )}
      </div>

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
            <button
              key={item.name}
              onClick={handleClick}
              className={clsx(
                'group flex h-10 cursor-pointer items-center rounded-lg',
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
          );
        })}
      </div>

      {/* 질문 목록 */}
      {isOpen && (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex h-7 items-center px-2.5">
            <span className="text-body-xsmall text-gray-70">내 질문</span>
            <ArrowRight className="h-5 w-5 text-gray-50" />
          </div>
          <div className="mt-2 flex flex-col overflow-y-auto">
            {queryItems.map((query) => {
              return (
                <button
                  key={query.id}
                  // , isActive ? selectedClass : defaultClass
                  className={clsx('group flex cursor-pointer rounded-lg py-2')}
                >
                  {/* , isActive ? 'text-blue-55' : 'text-gray-80' */}
                  <span className={clsx('text-body-small truncate px-2.5')}>{query.content}</span>
                  <span className="mr-2.5 ml-auto flex h-5 w-5 items-center opacity-0 transition-opacity group-hover:opacity-100">
                    <Kebeb className="text-gray-50" />
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 유저 */}
      <div className={'mt-auto flex flex-col gap-1.5'}>
        {isOpen && <div className={`border-neutral-3 relative right-2 w-60 border`} />}
        <div
          className={clsx(
            'outline-gray flex h-13.5 cursor-pointer items-center rounded-lg',
            isOpen ? 'w-56.25 justify-between px-1.5 py-1' : 'justify-center',
          )}
        >
          <div className={clsx('flex gap-4', isOpen ? 'mt-auto' : '')}>
            <DefaultProfile className="h-10 w-10" />
            {isOpen && (
              <div className="relative top-px">
                <div className="text-heading-small text-gray-80">{user?.name ?? '이름없음'}</div>
                <div className="text-body-small text-gray-50">사업 개발</div>
              </div>
            )}
          </div>
          {isOpen && (
            <div className="relative bottom-1 flex cursor-pointer items-center p-0.5">
              <UnfoldMore className="relative top-px h-6 w-6" />
            </div>
          )}
        </div>
      </div>
    </nav>
  );
};

export default SideNavBar;
