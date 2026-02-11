'use client';

import { usePathname, useRouter } from 'next/navigation';

import { useSidebarStore } from '@/shared/store/sidebarStore';
import { cn } from '@/shared/utils/cn';

import ArticlePerson from '/public/icons/icon/article_person.svg';
import CheckCircle from '/public/icons/icon/check_circle.svg';
import Clock from '/public/icons/icon/clock.svg';
import CloudCheck from '/public/icons/icon/cloud_check.svg';
import Explore from '/public/icons/icon/explore.svg';
import Group from '/public/icons/icon/group.svg';
import Help from '/public/icons/icon/help.svg';
import Lock from '/public/icons/icon/lock.svg';
import Person from '/public/icons/icon/person.svg';
import Send from '/public/icons/icon/send.svg';
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

const SETTINGS_SECTIONS: SettingsSection[] = [
  {
    label: '내 설정',
    items: [
      { name: '계정', href: '/mypage/settings', Icon: Person },
      { name: '협업툴 연동', href: '/mypage/integrations', Icon: CloudCheck },
      { name: '개인 맞춤 설정', href: '/mypage/preferences', Icon: Explore },
      { name: '질문 히스토리', href: '/mypage/history', Icon: Clock },
    ],
  },
  {
    label: '조직 관리',
    items: [
      { name: '조직도', href: '/team', Icon: Tree },
      { name: '이용자 관리', href: '/team/members', Icon: Group },
      { name: '이용자 활동 기록', href: '/team/activity', Icon: ArticlePerson },
      { name: '감사 로그', href: '/team/audit', Icon: ArticlePerson },
    ],
  },
  {
    label: '권한 관리',
    items: [
      { name: '권한 정보', href: '/team/permissions', Icon: Lock },
      { name: '권한 신청', href: '/team/permissions/request', Icon: Send },
      { name: '권한 승인', href: '/team/permissions/approve', Icon: CheckCircle },
    ],
  },
  {
    label: '지원',
    items: [{ name: '도움말', href: '/help', Icon: Help }],
  },
];

const SettingsPanel = () => {
  const pathname = usePathname();
  const router = useRouter();
  const { setActivePanel } = useSidebarStore();

  const handleClick = (href: string) => {
    setActivePanel(null);
    router.push(href);
  };

  return (
    <div className="border-neutral-3 flex h-screen w-60 shrink-0 flex-col gap-5 border-r bg-white px-2 py-5">
      {SETTINGS_SECTIONS.map((section) => (
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
                      ? 'border-neutral-2 bg-blue-1 border text-blue-50'
                      : 'border border-transparent bg-white text-gray-80 hover:bg-neutral-2',
                  )}
                >
                  <item.Icon
                    className={cn('h-6 w-6 shrink-0', isActive ? 'text-blue-50' : 'text-gray-50')}
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
