'use client';

import clsx from 'clsx';
import { useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import DefaultProfile from '/public/icons/icon/profile.svg';
import Person from '/public/icons/icon/person.svg';
import AdminPanelSettings from '/public/icons/icon/admin_panel_settings.svg';
import Settings from '/public/icons/icon/settings.svg';
import Logout from '/public/icons/icon/logout.svg';
import { useEscapeKey } from '@/shared/hooks/useEscapeKey';
import { useOutsideClick } from '@/shared/hooks/useOutsideClick';
import { logout } from '@/shared/api/auth';

interface UserModalProps {
  onClose: () => void;
  userName?: string;
  userEmail?: string;
}

const UserModal = ({ onClose, userName, userEmail }: UserModalProps) => {
  const router = useRouter();
  const modalRef = useRef<HTMLDivElement>(null);
  const [isDarkMode, setIsDarkMode] = useState(false);

  useEscapeKey(onClose);
  useOutsideClick(modalRef, onClose);

  const handleLogout = async () => {
    onClose(); // 모달 close
    await logout();
  };

  return (
    <div
      ref={modalRef}
      className="shadow-dropdown-menu border-neutral-4 flex w-62.5 flex-col gap-3 rounded-2xl border bg-white px-1.5 py-2"
    >
      {/* 헤더 (프로필 정보) */}
      <div className="flex h-12 items-center gap-4 px-1">
        <DefaultProfile className="h-10 w-10 shrink-0" />
        <div className="relative top-px flex min-w-0 flex-col">
          <span className="text-heading-small text-gray-80 truncate">{userName ?? '이름없음'}</span>
          <span className="text-body-small truncate text-gray-50">{userEmail ?? ''}</span>
        </div>
      </div>
      {/* 메뉴 */}
      <div className="flex flex-col gap-2">
        <div className="flex flex-col gap-1">
          <button
            onClick={() => {
              onClose();
              router.push('/mypage');
            }}
            className="icon-button-only-gray flex cursor-pointer items-center gap-2.5 p-2"
          >
            <Person className="text-gray-70 h-6 w-6" />
            <span className="text-body-small text-gray-80">마이페이지</span>
          </button>
          <button className="icon-button-only-gray flex cursor-pointer items-center gap-2.5 p-2">
            <AdminPanelSettings className="text-gray-70 h-6 w-6" />
            <span className="text-body-small text-gray-80">권한 설정</span>
          </button>
          <button className="icon-button-only-gray flex cursor-pointer items-center gap-2.5 p-2">
            <Settings className="text-gray-70 h-6 w-6" />
            <span className="text-body-small text-gray-80">환경 설정</span>
          </button>
        </div>
        <div className="bg-neutral-1 border-neutral-2 -mt-1.5 flex h-10 w-59.5 gap-1 rounded-lg border p-0.5">
          <button
            onClick={() => setIsDarkMode(false)}
            className={clsx(
              'text-body-small text-gray-80 flex w-28.75 cursor-pointer items-center justify-center py-1.5',
              isDarkMode ? '' : 'shadow-button border-neutral-3 rounded-lg border bg-white',
            )}
          >
            라이트 모드
          </button>
          <button
            onClick={() => setIsDarkMode(true)}
            className={clsx(
              'text-body-small text-gray-80 flex w-28.75 cursor-pointer items-center justify-center py-1.5',
              isDarkMode ? 'shadow-button border-neutral-3 rounded-lg border bg-white' : ' ',
            )}
          >
            다크 모드
          </button>
        </div>
      </div>
      {/* divider */}
      <div className="bg-neutral-3 flex h-px w-full items-center" />
      {/* 로그아웃 */}
      <button onClick={handleLogout} className="icon-button-only-gray flex cursor-pointer items-center gap-2.5 p-2">
        <Logout className="text-gray-70 h-6 w-6" />
        <span className="text-body-small text-gray-80">로그아웃</span>
      </button>
    </div>
  );
};

export default UserModal;
