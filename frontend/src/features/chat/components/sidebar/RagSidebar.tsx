'use client';

import { useState } from 'react';

import type { QAPair } from '@/features/chat/utils/chat';

import SidebarHeader from './SidebarHeader';
import SourceList from './source/SourceList';
import TaskList from './tasks/TaskList';

interface RagSidebarProps {
  currentQA: QAPair | undefined;
  isLoading: boolean;
  isError: boolean;
}

const RagSidebar = ({ currentQA, isLoading, isError }: RagSidebarProps) => {
  const [activeTab, setActiveTab] = useState<'source' | 'detail'>('source');

  const sourceCount = currentQA?.answer?.sources?.length ?? 0;
  const sources = currentQA?.answer?.sources ?? [];
  const tasks = currentQA?.answer?.detailed_tasks ?? [];

  return (
    <div className="border-neutral-3 flex w-115 flex-none flex-col border-l bg-white">
      <SidebarHeader
        activeTab={activeTab}
        onChange={setActiveTab}
        sourceCount={sourceCount}
      />
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'source' && (
          <SourceList
            sources={sources}
            isLoading={isLoading}
            isError={isError}
          />
        )}
        {activeTab === 'detail' && (
          <TaskList
            tasks={tasks}
            isLoading={isLoading}
          />
        )}
      </div>
    </div>
  );
};

export default RagSidebar;
