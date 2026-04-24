'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import Add from '@/public/icons/icon/add_small.svg';
import AI from '@/public/icons/icon/ai.svg';
import ArrowRight2 from '@/public/icons/icon/arrow_right2.svg';
import Kebeb from '@/public/icons/icon/kebeb 2.svg';
import { MoreButtonContent } from '@/shared/components/layout/topNavbar/MoreButtonModal';
import { Button } from '@/shared/components/ui/button';
import { DropdownMenu, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { cn } from '@/shared/utils/cn';
import { isValidSessionId } from '@/shared/utils/sessionId';

import SessionQuestionsModal from './SessionQuestionsModal';

interface RagHeaderProps {
  title: string;
  sessionId: string;
}

export default function RagHeader({ title, sessionId }: RagHeaderProps) {
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
      <div className="border-r-edge-neutral border-b-edge-neutral border-r-0.5 bg-fill-normal sticky top-0 z-base flex h-13 justify-between border-b px-6 py-2">
        {/* 좌측 메뉴 */}
        <div className="relative flex min-w-0 items-center">
          <button
            onClick={() => {
              setActivePanel('questionsHistory');
            }}
            className={cn(
              'icon-button-only-gray flex items-center rounded-xl px-2 py-1',
              isQuestionsHistoryPanelOpen && 'bg-fill-interaction-pressed rounded-xl',
            )}
          >
            <AI className="text-content-alternative h-5 w-5" />
            <span className={`text-heading-small text-content-alternative ml-1.5 hidden cursor-pointer lg:inline`}>
              캐치스턴트 AI
            </span>
          </button>
          <ArrowRight2 className="text-content-alternative h-5 w-5" />
          <button
            onClick={handleTitleClick}
            className="text-heading-small text-content-normal! hover:bg-fill-interaction-hover max-w-50 cursor-pointer truncate rounded-lg px-2 py-1 transition-colors"
          >
            {title}
          </button>

          {/* 세션 질문 목록 모달 */}
          {isSessionQuestionsOpen && (
            <div className="absolute top-full left-0 z-local mt-1">
              <SessionQuestionsModal
                sessionId={sessionId}
                onClose={() => setIsSessionQuestionsOpen(false)}
                onSelect={handleSelectQuestion}
              />
            </div>
          )}
        </div>

        {/* 우측 메뉴 */}
        <div className="flex shrink-0 items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="icon-only-gray" size="md">
                <Kebeb className="h-6 w-6" />
              </Button>
            </DropdownMenuTrigger>
            <MoreButtonContent />
          </DropdownMenu>
          <Button variant="box-outline-gray" size="md" onClick={handleNewQuestion}>
            <Add className="text-content-neutral h-5 w-5" />
            <span className="text-content-neutral whitespace-nowrap">새 업무 질문</span>
          </Button>
        </div>
      </div>
    </>
  );
}
