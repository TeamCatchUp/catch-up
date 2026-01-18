'use client';

import clsx from 'clsx';
import { useState } from 'react';
import AI from '/public/icons/icon/ai.svg';
import ArrowRight2 from '/public/icons/icon/arrow_right2.svg';
import Add from '/public/icons/icon/add_small.svg';
import Share from '/public/icons/icon/share_2.svg';
import Kebeb from '/public/icons/icon/kebeb 2.svg';
import CatchAssistantModal from '@/components/rag/modal/CatchAssistantModal';
import QuestionsListModal from '@/components/rag/modal/QuestionsListInSessionModal';

const RagHeader = () => {
  const [isCatchModalOpen, setIsCatchModalOpen] = useState(false);
  const [isQuestionsListOpen, setIsQuestionsListOpen] = useState(false);

  return (
    <>
      <div className="border-r-neutral-3 border-b-neutral-3 sticky top-0 z-100 flex min-w-240.75 justify-between border-r border-b bg-white px-16 py-2">
        {/* 좌측 메뉴 */}
        <div className="relative flex items-center">
          <button
            onClick={() => {
              setIsQuestionsListOpen(false);
              setIsCatchModalOpen(true);
            }}
            className={clsx(
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
            className={clsx(
              'text-heading-small text-gray-80! icon-button-only-gray max-w-50 cursor-pointer truncate rounded-xl px-2 py-1',
              isQuestionsListOpen && 'bg-neutral-3 rounded-xl',
            )}
          >
            현재페이지현재페이지현재페이지
          </button>
          {/* 대화 내 질문 목록 모달 */}
          {isQuestionsListOpen && (
            <div className="absolute top-8.5 left-35">
              <QuestionsListModal onClose={() => setIsQuestionsListOpen(false)} />
            </div>
          )}
        </div>

        {/* 우측 메뉴 */}
        <div className="flex items-center gap-1.5">
          <button
            className={`border-neutral-3 box-button-outline-gray flex w-29.75 cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1.5`}
          >
            <Add className="text-gray-70 flex h-5 w-5" />
            <span className={`text-body-small text-gray-70 whitespace-nowrap`}>새 업무 질문</span>
          </button>
          <button className={`icon-button-only-gray flex items-center rounded-lg p-1.5`}>
            <Share className="h-6 w-6 cursor-pointer text-gray-50" />
          </button>
          <button className={`icon-button-only-gray flex items-center rounded-lg p-1.5`}>
            <Kebeb className="h-6 w-6 cursor-pointer text-gray-50" />
          </button>
        </div>
      </div>

      {/* 캐치스턴트 모달 */}
      {isCatchModalOpen && (
        <div className="bg-alpha-white-50 fixed inset-0 z-1000 flex items-center justify-center">
          <CatchAssistantModal onClose={() => setIsCatchModalOpen(false)} />
        </div>
      )}
    </>
  );
};

export default RagHeader;
