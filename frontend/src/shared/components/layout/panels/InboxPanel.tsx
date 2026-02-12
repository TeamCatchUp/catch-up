'use client';

import { useState } from 'react';

import { cn } from '@/shared/utils/cn';

import AdminPanelSettings from '/public/icons/icon/admin_panel_settings.svg';
import Assignment from '/public/icons/icon/assignment.svg';
import CheckCircle from '/public/icons/icon/check_circle.svg';
import DefaultProfile from '/public/icons/icon/default_profile.svg';
import FilterList from '/public/icons/icon/filter_list.svg';
import Kebab2 from '/public/icons/icon/kebeb 2.svg';
import Settings from '/public/icons/icon/settings.svg';
import Share2 from '/public/icons/icon/share_2.svg';

type FilterTab = '모두' | '공유' | '보고' | '관리' | '요청';

const FILTER_TABS: FilterTab[] = ['모두', '공유', '보고', '관리', '요청'];

const CATEGORY_ICONS: Record<string, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  관리: Settings,
  공유: Share2,
  보고: Assignment,
  요청: AdminPanelSettings,
  승인: CheckCircle,
};

interface InboxItem {
  id: string;
  category: string;
  sender: string;
  title: string;
  preview: string;
  date: string;
  isRead: boolean;
}

const MOCK_INBOX_ITEMS: InboxItem[] = [
  {
    id: '1',
    category: '관리',
    sender: 'Jira',
    title: '의 연동이 필요합니다.',
    preview: '내용 text text text text text text text text text text text text text text text text',
    date: '2025.12.15',
    isRead: false,
  },
  {
    id: '2',
    category: '공유',
    sender: '팀원G',
    title: '님이 업무 자료를 공유했어요',
    preview: '내용 text text text text text text text text text text text text text text text text',
    date: '2025.12.15',
    isRead: false,
  },
  {
    id: '3',
    category: '보고',
    sender: '팀원G',
    title: '님의 업무 매뉴얼 권한 요청',
    preview: '내용 text text text text text text text text text text text text text text text text',
    date: '2025.12.15',
    isRead: true,
  },
  {
    id: '4',
    category: '요청',
    sender: '팀원G',
    title: '님의 상세정보 권한 요청',
    preview: '내용 text text text text text text text text text text text text text text text text',
    date: '2025.12.15',
    isRead: true,
  },
  {
    id: '5',
    category: '승인',
    sender: '팀원G',
    title: '님이 미팅을 수락함',
    preview: '내용 text text text text text text text text text text text text text text text text',
    date: '2025.12.15',
    isRead: true,
  },
  {
    id: '6',
    category: '승인',
    sender: '팀원G',
    title: '님이 미팅을 수락함',
    preview: '내용 text text text text text text text text text text text text text text text text',
    date: '2025.12.15',
    isRead: true,
  },
  {
    id: '7',
    category: '승인',
    sender: '팀원G',
    title: '님이 미팅을 수락함',
    preview: '내용 text text text text text text text text text text text text text text text text',
    date: '2025.12.15',
    isRead: true,
  },
  {
    id: '8',
    category: '승인',
    sender: '팀원G',
    title: '님이 미팅을 수락함',
    preview: '내용 text text text text text text text text text text text text text text text text',
    date: '2025.12.15',
    isRead: true,
  },
];

const InboxPanel = () => {
  const [activeTab, setActiveTab] = useState<FilterTab>('모두');

  const filteredItems =
    activeTab === '모두' ? MOCK_INBOX_ITEMS : MOCK_INBOX_ITEMS.filter((item) => item.category === activeTab);

  return (
    <div className="border-neutral-3 flex h-screen w-[418px] shrink-0 flex-col gap-4 border-r bg-white py-5 shadow-panel">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4">
        <span className="text-heading-large text-gray-80">수신함</span>
        <div className="flex gap-1.5">
          <button className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg hover:bg-neutral-2">
            <FilterList className="h-6 w-6 text-gray-50" />
          </button>
          <button className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg hover:bg-neutral-2">
            <Kebab2 className="h-6 w-6 text-gray-50" />
          </button>
        </div>
      </div>

      {/* 필터 탭 + 알림 리스트 wrapper */}
      <div className="flex min-h-0 flex-1 flex-col gap-2.5 pb-5">
        {/* 필터 칩 */}
        <div className="flex gap-2 px-4">
          {FILTER_TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'text-body-small h-9 shrink-0 cursor-pointer rounded-full px-3 py-1.5 transition-colors',
                activeTab === tab
                  ? 'bg-neutral-80 text-white'
                  : 'border-neutral-3 border bg-white text-gray-70 hover:bg-neutral-2',
              )}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* 알림 리스트 */}
        <div className="flex flex-1 flex-col overflow-y-auto">
          {filteredItems.map((item) => {
            const CategoryIcon = CATEGORY_ICONS[item.category] ?? CheckCircle;

            return (
              <button
                key={item.id}
                className={cn(
                  'border-neutral-3 flex w-full cursor-pointer gap-2.5 border-b px-4 py-3 text-left transition-colors hover:bg-neutral-2',
                  item.isRead ? 'bg-white' : 'bg-blue-1',
                )}
              >
                {/* 프로필 + 카테고리 아이콘 */}
                <div className="relative shrink-0">
                  <DefaultProfile className="border-neutral-2 h-10 w-10 rounded-full border" />
                  <div className="absolute top-7 -right-0.5 rounded-full bg-white p-0.5">
                    <CategoryIcon className="h-4 w-4 text-blue-40" />
                  </div>
                </div>

                {/* 텍스트 */}
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  {/* 제목 + 날짜 */}
                  <div className="flex items-center gap-1.5">
                    <div className="text-body-small text-gray-80 min-w-0 flex-1 truncate">
                      <span>{item.sender}</span>
                      <span>{item.title}</span>
                    </div>
                    <span className="text-body-xsmall shrink-0 text-gray-30">{item.date}</span>
                  </div>
                  {/* 미리보기 */}
                  <p className="text-body-small line-clamp-2 text-gray-60">{item.preview}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default InboxPanel;
