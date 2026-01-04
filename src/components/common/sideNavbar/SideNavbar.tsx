'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import CatchupLogo from '/public/icons/logo/logo_catchup.svg';
import CatchupLogoLetter from '/public/icons/logo/logo_catchup_letter.svg';
import Close from '/public/icons/icon/close.svg';
import Open from '/public/icons/icon/open.svg';
import Home from '/public/icons/icon/home.svg';
import Search from '/public/icons/icon/search.svg';
import Dashboard from '/public/icons/icon/dashboard.svg';
import Stacks from '/public/icons/icon/stacks.svg';
import Mail from '/public/icons/icon/mail.svg';
import DefaultProfile from '/public/icons/icon/default_profile.svg';
import UnfoldMore from '/public/icons/icon/unfold_more.svg';

const navItems = [
  { name: '홈', href: '/', Icon: Home },
  { name: '업무이력 검색', href: '/search', Icon: Search },
  { name: '내 업무 관리하기', href: '/dashboard', Icon: Dashboard },
  { name: '인수인계 DB', href: '/stacks', Icon: Stacks },
  { name: '수신함', href: '/mail', Icon: Mail },
];

const SideNavbar = () => {
  const pathname = usePathname();
  const isRagAnswerPage = pathname === '/rag_answer';
  const [isOpen, setIsOpen] = useState(() => !isRagAnswerPage);

  return (
    <nav
      className={`border-neutral-3 flex h-full bg-white ${isOpen ? 'w-[241px] px-2 py-2.5' : 'w-[61px] items-center py-5'} flex-col gap-4 border-r`}
    >
      <div className={`flex ${isOpen ? 'items-center justify-between' : ''}`}>
        <div className={`flex items-center gap-2.5 ${isOpen ? 'px-1' : ''}`}>
          <div className="group border-neutral-3 relative flex h-10 w-10 cursor-pointer items-center rounded-xl border-[0.5px] px-[5px] py-1.5">
            <CatchupLogo className="relative left-px h-[30px] w-7" />

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

      <div className={`flex flex-col ${isOpen ? 'gap-1' : 'gap-2'}`}>
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex h-10 cursor-pointer items-center rounded-lg border-none ${isOpen ? 'w-[226px] gap-3 px-2.5 py-2' : 'w-10 items-center justify-center'} ${isActive ? 'bg-blue-1 border-neutral-1' : ''}`}
            >
              <item.Icon
                className={`${isOpen ? 'h-5.5 w-5.5' : 'h-7 w-7'} ${isActive ? 'text-blue-50' : 'text-gray-70'}`}
              />
              {isOpen && (
                <span className={`text-body-small relative ${isActive ? 'text-blue-55' : 'text-gray-80'}`}>
                  {item.name}
                </span>
              )}
              {item.name === '수신함' && (
                <div className="rounded-md2 bg-blue-1 border-blue-30 ml-auto flex h-[23px] w-[23px] items-center justify-center border-[0.5px] px-0.5">
                  <span className="text-body-small text-blue-40">2</span>
                </div>
              )}
            </Link>
          );
        })}
      </div>

      {isOpen && <div className={`border-neutral-3 absolute bottom-[70px] left-0 w-60 border`} />}

      <div
        className={`absolute bottom-2.5 flex h-[54px] ${isOpen ? 'w-[225px] justify-between px-1.5 py-1' : 'justify-center'}`}
      >
        <div className={`flex cursor-pointer items-center ${isOpen ? 'gap-4' : 'justify-center'}`}>
          <DefaultProfile className="h-10 w-10" />
          {isOpen && (
            <div className="relative top-px">
              <div className="text-heading-small text-gray-80">이진수</div>
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
    </nav>
  );
};

export default SideNavbar;
