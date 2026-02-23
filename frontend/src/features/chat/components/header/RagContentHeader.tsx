'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import { MoreButtonContent } from '@/shared/components/layout/topNavbar/MoreButtonModal';
import { DropdownMenu, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { cn } from '@/shared/utils/cn';
import { isValidSessionId } from '@/shared/utils/sessionId';

import SessionQuestionsModal from './SessionQuestionsModal';

import Add from '/public/icons/icon/add_small.svg';
import AI from '/public/icons/icon/ai.svg';
import ArrowRight2 from '/public/icons/icon/arrow_right2.svg';
import Kebeb from '/public/icons/icon/kebeb 2.svg';

interface RagHeaderProps {
  title: string;
  sessionId: string;
}

const RagHeader = ({ title, sessionId }: RagHeaderProps) => {
  const { activePanel, setActivePanel } = useSidebarStore();
  const router = useRouter();
  const isQuestionsHistoryPanelOpen = activePanel === 'questionsHistory';
  const [isSessionQuestionsOpen, setIsSessionQuestionsOpen] = useState(false);

  const handleNewQuestion = () => {
    router.push(`/search`);

    setActivePanel(null);
  };

  const handleTitleClick = () => {
    if (isValidSessionId(sessionId)) {
      setIsSessionQuestionsOpen((prev) => !prev);
    }
  };

  const handleSelectQuestion = (messageId: number) => {
    setIsSessionQuestionsOpen(false);
    router.push(`/chat/${sessionId}?scrollTo=${messageId}`);
  };

  return (
    <>
      <div className="border-r-neutral-3 border-b-neutral-3 border-r-0.5 sticky top-0 z-10 flex h-13 justify-between border-b bg-white px-6 py-2 lg:px-16">
        {/* 좌측 메뉴 */}
        <div className="relative flex min-w-0 items-center">
          <button
            onClick={() => {
              setActivePanel('questionsHistory');
            }}
            className={cn(
              'icon-button-only-gray flex items-center rounded-xl px-2 py-1',
              isQuestionsHistoryPanelOpen && 'bg-neutral-3 rounded-xl',
            )}
          >
            <AI className="h-5 w-5 text-gray-50" />
            <span className={`text-heading-small ml-1.5 hidden cursor-pointer text-gray-50 lg:inline`}>
              캐치스턴트 AI
            </span>
          </button>
          <ArrowRight2 className="h-5 w-5 text-gray-50" />
          <button
            onClick={handleTitleClick}
            className="text-heading-small text-gray-80! max-w-50 cursor-pointer truncate px-2 py-1 hover:bg-neutral-2 rounded-lg transition-colors"
          >
            {title}
          </button>

          {/* 세션 질문 목록 모달 */}
          {isSessionQuestionsOpen && (
            <div className="absolute top-full left-0 z-20 mt-1">
              <SessionQuestionsModal
                sessionId={sessionId}
                onClose={() => setIsSessionQuestionsOpen(false)}
                onSelect={handleSelectQuestion}
              />
            </div>
          )}
        </div>

        {/* 우측 메뉴 */}
        <div className="flex shrink-0 items-center gap-1.5">
          <button
            onClick={handleNewQuestion}
            className={`border-neutral-3 box-button-outline-gray flex w-29.75 cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1.5`}
          >
            <Add className="text-gray-70 flex h-5 w-5" />
            <span className={`text-body-small text-gray-70 whitespace-nowrap`}>새 업무 질문</span>
          </button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="border-neutral-3 hover:border-neutral-4 hover:bg-neutral-2 active:border-neutral-5 active:bg-neutral-3 data-[state=open]:border-neutral-4 data-[state=open]:bg-neutral-2 cursor-pointer rounded-lg border bg-white px-1.5 py-1.5 transition-colors">
                <Kebeb className="text-gray-70 h-6 w-6" />
              </button>
            </DropdownMenuTrigger>
            <MoreButtonContent />
          </DropdownMenu>
        </div>
      </div>
    </>
  );
};

export default RagHeader;
