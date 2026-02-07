'use client';

import { useState } from 'react';
import type { QAPair } from '@/util/ragAnswer/chat';
import RagRightAdditionalHeader from '@/components/ragAnswer/components/rightComponent/sourceComponent/RagRightAdditionalHeader';
import SourceComponent from '@/components/ragAnswer/components/rightComponent/sourceComponent/SourceComponent';
import DetailedTasksComponent from '@/components/ragAnswer/components/rightComponent/detailedTasksComponent/DetailedTasksComponent';

interface RagSidebarProps {
  currentQA: QAPair | undefined;
  isLoading: boolean;
  isError: boolean;
}

const RagSidebar = ({ currentQA, isLoading, isError }: RagSidebarProps) => {
  const [activeTab, setActiveTab] = useState<'source' | 'detail'>('source');

  const sourceCount = currentQA?.answer?.sources?.length ?? 0;
  const sources = currentQA?.answer?.sources ?? [];
  const tasks = currentQA?.answer?.detailedTasks ?? [];

  return (
    <div className="border-neutral-3 flex w-115 flex-none flex-col border-l bg-white">
      <RagRightAdditionalHeader
        activeTab={activeTab}
        onChange={setActiveTab}
        sourceCount={sourceCount}
      />
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'source' && (
          <SourceComponent
            sources={sources}
            isLoading={isLoading}
            isError={isError}
          />
        )}
        {activeTab === 'detail' && (
          <DetailedTasksComponent
            tasks={tasks}
            isLoading={isLoading}
          />
        )}
      </div>
    </div>
  );
};

export default RagSidebar;
