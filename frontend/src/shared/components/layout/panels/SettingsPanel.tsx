'use client';

import { usePathname, useRouter } from 'next/navigation';

import type { UserRole } from '@/shared/queries/auth.types';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { useUserStore } from '@/shared/store/userStore';
import { cn } from '@/shared/utils/cn';

import AdminPanelSettings from '/public/icons/icon/admin_panel_settings.svg';
import ArticlePerson from '/public/icons/icon/article_person.svg';
import Clock from '/public/icons/icon/clock.svg';
import CloudCheck from '/public/icons/icon/cloud_check.svg';
import Explore from '/public/icons/icon/explore.svg';
import Group from '/public/icons/icon/group.svg';
import Help from '/public/icons/icon/help.svg';
import Lock from '/public/icons/icon/lock.svg';
import Person from '/public/icons/icon/person.svg';
import Tree from '/public/icons/icon/tree.svg';

interface SettingsMenuItem {
  name: string;
  href: string;
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
}

interface SettingsSection {
  label: string;
  items: SettingsMenuItem[];
}

/**
 * 사용자 권한별 설정 패널 섹션과 메뉴를 정의
 */
const SETTINGS_SECTIONS_BY_ROLE: Record<UserRole, SettingsSection[]> = {
  user: [
    {
      label: '내 설정',
      items: [
        { name: '계정', href: '/mypage/profile', Icon: Person },
        { name: '협업툴 연동', href: '/mypage/integrations', Icon: CloudCheck },
        { name: '개인 맞춤 설정', href: '/mypage/preferences', Icon: Explore },
        { name: '질문 히스토리', href: '/mypage/history', Icon: Clock },
        { name: '도움말', href: '/mypage/help', Icon: Help },
      ],
    },
  ],
  admin: [
    {
      label: '내 설정',
      items: [
        { name: '계정', href: '/mypage/profile', Icon: Person },
        { name: '협업툴 연동', href: '/mypage/integrations', Icon: CloudCheck },
        { name: '개인 맞춤 설정', href: '/mypage/preferences', Icon: Explore },
        { name: '질문 히스토리', href: '/mypage/history', Icon: Clock },
      ],
    },
    {
      label: '조직 관리',
      items: [
        { name: '조직도', href: '/admin/organization', Icon: Tree },
        { name: '이용자 관리', href: '/admin/members', Icon: Group },
        { name: '이용자 질문 기록', href: '/admin/question-logs', Icon: ArticlePerson },
        { name: '감사 로그', href: '/admin/audit-logs', Icon: AdminPanelSettings },
      ],
    },
    {
      label: '권한 관리',
      items: [{ name: '권한 정보', href: '/admin/permissions', Icon: Lock }],
    },
    {
      label: '지원',
      items: [{ name: '도움말', href: '/mypage/help', Icon: Help }],
    },
  ],
};

/**
 * 좌측 설정 패널 렌더링 및 메뉴 라우팅을 처리
 */
const SettingsPanel = () => {
  const pathname = usePathname();
  const router = useRouter();
  const userRole = useUserStore((state) => state.user?.role);
  const role: UserRole = userRole === 'admin' ? 'admin' : 'user';
  const { setActivePanel } = useSidebarStore();

  const handleClick = (href: string) => {
    setActivePanel('settings');
    router.push(href);
  };

  return (
    <div className="border-neutral-3 flex h-screen w-60 shrink-0 flex-col gap-5 border-r bg-white px-2 py-5">
      {SETTINGS_SECTIONS_BY_ROLE[role].map((section) => (
        <div key={section.label} className="flex flex-col gap-1.5">
          <div className="px-1">
            <span className="text-body-xsmall font-medium text-gray-60">{section.label}</span>
          </div>
          <div className="flex flex-col gap-1">
            {section.items.map((item) => {
              const isActive = pathname === item.href;

              return (
                <button
                  key={item.href}
                  onClick={() => handleClick(item.href)}
                  className={cn(
                    'flex h-10 w-full cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 transition-colors',
                    isActive
                      ? 'border-neutral-2 border bg-blue-1 text-blue-50'
                      : 'border border-transparent bg-white text-gray-80 hover:bg-neutral-2',
                  )}
                >
                  <item.Icon
                    className={cn('h-6 w-6 shrink-0', isActive ? 'text-blue-50' : 'text-gray-70')}
                  />
                  <span className="text-body-small">{item.name}</span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};

export default SettingsPanel;
