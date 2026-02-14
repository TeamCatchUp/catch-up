'use client';

import type { QAPair } from '@/features/chat/utils/render/chat';

import SidebarHeader from './SidebarHeader';
import SourceList from './source/SourceList';

interface RagSidebarProps {
  currentQA: QAPair | undefined;
  isLoading: boolean;
  isError: boolean;
}

const RagSidebar = ({ currentQA, isLoading, isError }: RagSidebarProps) => {
  const sources = currentQA?.answer?.sources ?? [];
  const sourceCount = sources.filter((source) => source.is_cited).length;
  const answerContent = currentQA?.answer?.content ?? '';

  return (
    <div className="border-neutral-3 flex w-100 flex-none flex-col border-l bg-white">
      <SidebarHeader sourceCount={sourceCount} />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <SourceList sources={sources} answerContent={answerContent} isLoading={isLoading} isError={isError} />
      </div>
    </div>
  );
};

export default RagSidebar;
