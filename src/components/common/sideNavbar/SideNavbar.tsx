'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import CatchupLogo from '@/assets/svgs/logo/logo_catchup.svg';
import CatchupLogoLetter from '@/assets/svgs/logo/logo_catchup_letter.svg';
import Close from '@/assets/svgs/navbar/close.svg';
import Home from '@/assets/svgs/navbar/home.svg';
import Search from '@/assets/svgs/navbar/search.svg';
import Dashboard from '@/assets/svgs/navbar/dashboard.svg';
import Stacks from '@/assets/svgs/navbar/stacks.svg';
import Mail from '@/assets/svgs/navbar/mail.svg';
import DefaultProfile from '@/assets/svgs/navbar/default_profile.svg';
import UnfoldMore from '@/assets/svgs/navbar/unfold_more.svg';

const navItems = [
  { name: '홈', href: '/', Icon: Home },
  { name: '업무이력 검색', href: '/search', Icon: Search },
  { name: '내 업무 관리하기', href: '/dashboard', Icon: Dashboard },
  { name: '인수인계 DB', href: '/stacks', Icon: Stacks },
  { name: '수신함', href: '/mail', Icon: Mail },
];

const SideNavbar = () => {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(true);

  return (
    <nav className={`border-neutral-3 flex h-full ${isOpen ? 'w-[241px]' : 'w-[62px]'} flex-col gap-4 border-r px-2`}>
      <div className={`flex items-center justify-between px-1 pt-2.5`}>
        <div onClick={() => !isOpen && setIsOpen(true)} className="flex items-center gap-2.5">
          <div className="border-neutral-3 flex h-10 w-10 cursor-pointer items-center rounded-xl border-[0.5px] px-[5px] py-1.5">
            <CatchupLogo className="relative left-px h-[20.53px] w-[27px]" />
          </div>
          <div className="relative top-0.5 flex items-center">{isOpen && <CatchupLogoLetter />}</div>
        </div>
        {isOpen && (
          <Close
            onClick={() => setIsOpen(false)}
            className="relative right-0.5 h-6 w-6 cursor-pointer p-0.5 text-gray-50"
          />
        )}
      </div>

      <div className="flex flex-col gap-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex h-10 cursor-pointer items-center gap-3 rounded-lg border border-none px-2.5 py-2 ${isOpen ? 'w-[226px]' : 'w-12'} ${isActive ? 'bg-blue-1 border-neutral-1' : ''}`}
            >
              <item.Icon className={`h-5.5 w-5.5 ${isActive ? 'text-blue-50' : 'text-gray-70'}`} />
              {isOpen && (
                <span
                  className={`text-body-small relative ${item.name === '홈' ? 'top-[1.5px]' : 'top-px'} ${isActive ? 'text-blue-55' : 'text-gray-80'}`}
                >
                  {item.name}
                </span>
              )}
            </Link>
          );
        })}
      </div>

      {isOpen && <div className={`border-neutral-3 'w-60' absolute bottom-[70px] left-0 border`} />}

      <div className="absolute bottom-2.5 flex w-[225px] justify-between px-1.5 py-1">
        <div className="flex cursor-pointer items-center gap-4">
          <DefaultProfile className="relative right-1 h-10 w-10" />
          {isOpen && (
            <div>
              <div className="text-heading-small text-gray-80">이진수</div>
              <div className="text-body-small text-gray-50">사업 개발</div>
            </div>
          )}
        </div>
        {isOpen && (
          <div className="relative bottom-1 flex cursor-pointer items-center p-0.5">
            <UnfoldMore className="h-6 w-6" />
          </div>
        )}
      </div>
    </nav>
  );
};

export default SideNavbar;
