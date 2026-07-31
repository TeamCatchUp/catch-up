'use client';

import { usePathname, useRouter } from 'next/navigation';

import IconArrowBack from '@/public/icons/icon/arrow_back.svg';
import IconArticlePerson from '@/public/icons/icon/article_person.svg';
import IconBuilding from '@/public/icons/icon/building.svg';
import IconClock from '@/public/icons/icon/clock.svg';
import IconFilter2 from '@/public/icons/icon/filter-2.svg';
import IconGraphOutline from '@/public/icons/icon/graph_outline.svg';
import IconGroup from '@/public/icons/icon/group.svg';
import IconHelp from '@/public/icons/icon/help.svg';
import IconHistory from '@/public/icons/icon/history.svg';
import IconLink from '@/public/icons/icon/link.svg';
import IconLock from '@/public/icons/icon/lock.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconPlugin from '@/public/icons/icon/plugin.svg';
import type { UserRole } from '@/shared/queries/auth.types';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { useUserStore } from '@/shared/store/userStore';

import SettingsNavGroup, { type SettingsNavGroupChild } from './SettingsNavGroup';
import SnbMenuItem from './SnbMenuItem';

interface SettingsMenuItem {
  kind: 'item';
  name: string;
  href: string;
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
}

interface SettingsMenuGroup {
  kind: 'group';
  name: string;
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  items: SettingsNavGroupChild[];
}

type SettingsEntry = SettingsMenuItem | SettingsMenuGroup;

interface SettingsSection {
  label: string;
  entries: SettingsEntry[];
}

/**
 * 사용자 권한별 설정 패널 섹션과 메뉴.
 * Figma 마스터 `Settings SNB`(5181:83143 루트어드민 / 5851:72323 팀원) 기준이다.
 * Catch Up MCP는 라우트가 없어 제외했다 — 준비되면 여기에 한 줄 추가한다.
 */
const SETTINGS_SECTIONS_BY_ROLE: Record<UserRole, SettingsSection[]> = {
  user: [
    {
      label: '내 설정',
      entries: [
        { kind: 'item', name: '계정', href: '/mypage/profile', Icon: IconPerson },
        { kind: 'item', name: '개인 맞춤 설정', href: '/mypage/preferences', Icon: IconFilter2 },
        { kind: 'item', name: '채팅 히스토리', href: '/mypage/history', Icon: IconClock },
        { kind: 'item', name: '토큰 사용량 관리', href: '/mypage/token-usage', Icon: IconGraphOutline },
      ],
    },
    {
      label: '지원',
      entries: [{ kind: 'item', name: '도움말', href: '/mypage/help', Icon: IconHelp }],
    },
  ],
  admin: [
    {
      label: '내 설정',
      entries: [
        { kind: 'item', name: '계정', href: '/mypage/profile', Icon: IconPerson },
        { kind: 'item', name: '개인 맞춤 설정', href: '/mypage/preferences', Icon: IconFilter2 },
        { kind: 'item', name: '채팅 히스토리', href: '/mypage/history', Icon: IconHistory },
      ],
    },
    {
      label: '조직 관리',
      entries: [
        {
          kind: 'group',
          name: '조직 협업툴 연동',
          Icon: IconBuilding,
          items: [
            { name: '커넥터 연결', href: '/admin/connectors', Icon: IconPlugin },
            { name: '이용자 매핑', href: '/admin/user-mapping', Icon: IconLink },
          ],
        },
        {
          kind: 'group',
          name: '멤버 관리',
          Icon: IconGroup,
          items: [
            { name: '멤버 정보', href: '/admin/members', Icon: IconPlugin },
            { name: '멤버 채팅 기록', href: '/admin/question-logs', Icon: IconArticlePerson },
          ],
        },
        { kind: 'item', name: '토큰 사용량 관리', href: '/admin/token-usage', Icon: IconGraphOutline },
        { kind: 'item', name: '권한 관리', href: '/admin/permissions', Icon: IconLock },
      ],
    },
    {
      label: '지원',
      entries: [{ kind: 'item', name: '도움말', href: '/mypage/help', Icon: IconHelp }],
    },
  ],
};

/** 좌측 설정 패널 렌더링 및 메뉴 라우팅 */
export default function SettingsPanel() {
  const pathname = usePathname();
  const router = useRouter();
  const userRole = useUserStore((state) => state.user?.role);
  const role: UserRole = userRole === 'admin' ? 'admin' : 'user';
  const { setActivePanel } = useSidebarStore();

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + '/');

  const handleClick = (href: string) => {
    setActivePanel('settings');
    router.push(href);
  };

  return (
    <div className="border-line-normal-neutral bg-fill-normal-normal flex h-screen w-60 shrink-0 flex-col gap-5 border-r px-2 py-3">
      <SnbMenuItem
        Icon={IconArrowBack}
        label="메인으로 가기"
        onClick={() => router.push('/')}
        className="border-line-normal-neutral shadow-card h-12 border"
      />

      {SETTINGS_SECTIONS_BY_ROLE[role].map((section) => (
        <div key={section.label} className="flex flex-col gap-1.5">
          <div className="px-2.5">
            <span className="text-body-xsmall text-text-normal-alternative font-medium">{section.label}</span>
          </div>
          <div className="flex flex-col">
            {section.entries.map((entry) =>
              entry.kind === 'group' ? (
                <SettingsNavGroup
                  key={entry.name}
                  label={entry.name}
                  Icon={entry.Icon}
                  items={entry.items}
                  activeHref={entry.items.find((item) => isActive(item.href))?.href ?? null}
                  onSelect={handleClick}
                  defaultExpanded={entry.items.some((item) => isActive(item.href))}
                />
              ) : (
                <SnbMenuItem
                  key={entry.href}
                  Icon={entry.Icon}
                  label={entry.name}
                  selected={isActive(entry.href)}
                  onClick={() => handleClick(entry.href)}
                />
              ),
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
