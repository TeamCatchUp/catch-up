'use client';

import type { QAPair } from '@/features/chat/utils/chat';

import SidebarHeader from './SidebarHeader';
import SourceList from './source/SourceList';

interface RagSidebarProps {
  currentQA: QAPair | undefined;
  isLoading: boolean;
  isError: boolean;
}

const RagSidebar = ({ currentQA, isLoading, isError }: RagSidebarProps) => {
  const sourceCount = currentQA?.answer?.sources?.length ?? 0;
  const sources = currentQA?.answer?.sources ?? [];

  return (
    <div className="border-neutral-3 flex w-100 flex-none flex-col border-l bg-white">
      <SidebarHeader sourceCount={sourceCount} />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <SourceList
          sources={sources}
          isLoading={isLoading}
          isError={isError}
        />
      </div>
    </div>
  );
};

export default RagSidebar;
