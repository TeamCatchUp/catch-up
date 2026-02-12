'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import { MoreButtonContent } from '@/shared/components/layout/topNavbar/MoreButtonModal';
import RecentQuestionsModal from '@/shared/components/layout/sideNavBar/modal/RecentQuestionsModal';
import { DropdownMenu, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

import SessionQuestionsModal from './SessionQuestionsModal';

import Add from '/public/icons/icon/add_small.svg';
import AI from '/public/icons/icon/ai.svg';
import ArrowRight2 from '/public/icons/icon/arrow_right2.svg';
import Kebeb from '/public/icons/icon/kebeb 2.svg';

interface RagHeaderProps {
  title: string;
  onSelectQuestion: (query: string) => void;
}

const RagHeader = ({ title, onSelectQuestion }: RagHeaderProps) => {
  const [isCatchModalOpen, setIsCatchModalOpen] = useState(false);
  const [isQuestionsListOpen, setIsQuestionsListOpen] = useState(false);
  const router = useRouter();

  const handleNewQuestion = () => {
    router.push(`/search`);

    setIsCatchModalOpen(false);
    setIsQuestionsListOpen(false);
  };

  return (
    <>
      <div className="border-r-neutral-3 border-b-neutral-3 border-r-0.5 sticky top-0 z-10 flex min-w-240.75 justify-between border-b bg-white px-16 py-2">
        {/* 좌측 메뉴 */}
        <div className="relative flex items-center">
          <button
            onClick={() => {
              setIsQuestionsListOpen(false);
              setIsCatchModalOpen(true);
            }}
            className={cn(
              'icon-button-only-gray flex items-center rounded-xl px-2 py-1',
              isCatchModalOpen && 'bg-neutral-3 rounded-xl',
            )}
          >
            <AI className="h-5 w-5 text-gray-50" />
            <span className={`text-heading-small ml-1.5 cursor-pointer text-gray-50`}>캐치스턴트 AI</span>
          </button>
          <ArrowRight2 className="h-5 w-5 text-gray-50" />
          <button
            onClick={() => {
              setIsCatchModalOpen(false);
              setIsQuestionsListOpen(true);
            }}
            className={cn(
              'text-heading-small text-gray-80! icon-button-only-gray max-w-50 cursor-pointer truncate rounded-xl px-2 py-1',
              isQuestionsListOpen && 'bg-neutral-3 rounded-xl',
            )}
          >
            {title}
          </button>
          {/* 대화 내 질문 목록 모달 */}
          {isQuestionsListOpen && (
            <div className="absolute top-8.5 left-35">
              <SessionQuestionsModal
                onClose={() => setIsQuestionsListOpen(false)}
                onSelect={(query) => {
                  onSelectQuestion(query);
                  setIsQuestionsListOpen(false);
                }}
              />
            </div>
          )}
        </div>

        {/* 우측 메뉴 */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleNewQuestion}
            className={`border-neutral-3 box-button-outline-gray flex w-29.75 cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1.5`}
          >
            <Add className="text-gray-70 flex h-5 w-5" />
            <span className={`text-body-small text-gray-70 whitespace-nowrap`}>새 업무 질문</span>
          </button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="cursor-pointer rounded-lg border border-neutral-3 bg-white px-1.5 py-1.5 transition-colors hover:border-neutral-4 hover:bg-neutral-2 active:border-neutral-5 active:bg-neutral-3 data-[state=open]:border-neutral-4 data-[state=open]:bg-neutral-2">
                <Kebeb className="text-gray-70 h-6 w-6" />
              </button>
            </DropdownMenuTrigger>
            <MoreButtonContent />
          </DropdownMenu>
        </div>
      </div>

      {/* 캐치스턴트 모달 */}
      {isCatchModalOpen && (
        <div className="bg-alpha-white-50 fixed inset-0 z-1000 flex items-center justify-center">
          <RecentQuestionsModal onClose={() => setIsCatchModalOpen(false)} />
        </div>
      )}
    </>
  );
};

export default RagHeader;
