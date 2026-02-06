/**
 * Sidebar Compound Component
 * 우측 사이드바 (Header, Tabs, Sources, Tasks)
 */

'use client';

import type { PropsWithChildren } from 'react';
import clsx from 'clsx';
import { useRagPageContext } from './Context';
import RagRightAdditionalHeader from '@/components/ragAnswer/components/rightComponent/sourceComponent/RagRightAdditionalHeader';
import SourceComponent from '@/components/ragAnswer/components/rightComponent/sourceComponent/SourceComponent';
import DetailedTasksComponent from '@/components/ragAnswer/components/rightComponent/detailedTasksComponent/DetailedTasksComponent';

/** Sidebar Root - 우측 고정 사이드바 컨테이너 */
interface SidebarProps extends PropsWithChildren {
  className?: string;
}

const Sidebar = ({ children, className }: SidebarProps) => {
  return (
    <div className={clsx('border-neutral-3 flex w-115 flex-none flex-col border-l bg-white', className)}>
      {children}
    </div>
  );
};

/** 사이드바 헤더 (탭 포함) */
const SidebarHeader = () => {
  const { pagination, ui } = useRagPageContext();
  const { currentQA } = pagination;

  const sourceCount = currentQA?.answer?.sources?.length ?? 0;

  return (
    <RagRightAdditionalHeader
      activeTab={ui.activeTab}
      onChange={ui.setActiveTab}
      sourceCount={sourceCount}
    />
  );
};

/** 사이드바 콘텐츠 영역 */
const SidebarContent = ({ children }: PropsWithChildren) => {
  return (
    <div className="flex-1 overflow-y-auto">
      {children}
    </div>
  );
};

/** 출처 탭 콘텐츠 */
const SidebarSources = () => {
  const { pagination, chat, ui } = useRagPageContext();
  const { currentQA } = pagination;

  if (ui.activeTab !== 'source') return null;

  const sources = currentQA?.answer?.sources ?? [];

  return (
    <SourceComponent
      sources={sources}
      isLoading={chat.isLoading}
      isError={chat.isError}
    />
  );
};

/** 상세 업무 탭 콘텐츠 */
const SidebarTasks = () => {
  const { pagination, chat, ui } = useRagPageContext();
  const { currentQA } = pagination;

  if (ui.activeTab !== 'detail') return null;

  const tasks = currentQA?.answer?.detailedTasks ?? [];

  return (
    <DetailedTasksComponent
      tasks={tasks}
      isLoading={chat.isLoading}
    />
  );
};

/** 전체 사이드바 렌더링 헬퍼 */
const SidebarFull = () => {
  return (
    <>
      <SidebarHeader />
      <SidebarContent>
        <SidebarSources />
        <SidebarTasks />
      </SidebarContent>
    </>
  );
};

/** Compound Component 조립 */
Sidebar.Header = SidebarHeader;
Sidebar.Content = SidebarContent;
Sidebar.Sources = SidebarSources;
Sidebar.Tasks = SidebarTasks;
Sidebar.Full = SidebarFull;

export default Sidebar;
