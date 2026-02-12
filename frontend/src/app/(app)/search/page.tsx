'use client';

import { useRef, useState } from 'react';
import Image from 'next/image';

import { GithubGuideCard, JiraGuideCard } from '@/features/search/components/GuideCard';
import IconLightbulb from '@/public/icons/icon/lightbulb.svg';
import Git from '@/public/image/aiGit.png';
import Jira from '@/public/image/AIJIRA1.png';
import TopNavbar from '@/shared/components/layout/topNavbar/TopNavbar';
import QueryBox from '@/shared/components/query/QueryBox';
import { useQuestionHistoryGate } from '@/shared/hooks/query/useQuestionHistoryGate';
import { useSearchFilters } from '@/shared/hooks/query/useSearchFilters';
import { useSearchInput } from '@/shared/hooks/query/useSearchInput';
import { useEscapeKey } from '@/shared/hooks/useEscapeKey';
import { useOutsideClick } from '@/shared/hooks/useOutsideClick';

export default function Search() {
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [activeCard, setActiveCard] = useState<'jira' | 'git' | null>(null);

  const filters = useSearchFilters();
  const input = useSearchInput({ inputRef });
  const { shouldShowNoHistoryBox } = useQuestionHistoryGate();
  const [isNoHistoryExpanded, setIsNoHistoryExpanded] = useState(true);

  // QueryBox 포커스 해제 + no-history 패널 닫기 공통 로직
  const handleClose = () => {
    input.setIsFocused(false);
    inputRef.current?.blur();
    if (shouldShowNoHistoryBox) {
      setIsNoHistoryExpanded(false);
    }
  };

  useEscapeKey(handleClose);

  useOutsideClick(containerRef, () => {
    if (filters.openPopover) return;
    handleClose();
  });

  const toggleCard = (type: 'jira' | 'git') => {
    setActiveCard(activeCard === type ? null : type);
  };

  return (
    <div className={`bg-home-gradient flex flex-[1_0_0] flex-col items-start self-stretch ${input.isFocused ? 'h-full overflow-hidden' : ''}`}>
      <TopNavbar pageType="search" />

      <div className="flex min-h-screen flex-col items-start self-stretch">
        {/* Query Section */}
        <div className="flex flex-col items-center gap-4 self-stretch pt-18 pb-18">
          {/* Hero */}
          <div className="flex h-24 flex-col items-center justify-center gap-3 text-gray-50">
            <h1 className="text-display-xlarge text-normal-normal">찾지 말고, 물어보세요.</h1>
            <p className="text-heading-large text-normal-alternative">
              Jira, GitHub, Wiki... 흩어진 정보를 모아 한 번에 알려드려요.
            </p>
          </div>

          {/* Query Box */}
          <QueryBox
            containerRef={containerRef}
            inputRef={inputRef}
            input={input}
            filters={filters}
            variant={shouldShowNoHistoryBox ? 'no-history' : 'default'}
            noHistoryExpanded={isNoHistoryExpanded || input.isFocused}
          />
        </div>

        {/* AI Guide Section */}
        <div
          className={`flex flex-col items-center gap-4 self-stretch px-52 pt-10 pb-30 transition-all duration-300 ${
            input.isFocused ? 'pointer-events-none translate-y-4 opacity-0' : 'opacity-100'
          }`}
        >
          <div className="flex w-190 flex-col items-center gap-3">
            <div className="flex items-center justify-between self-stretch">
              <div className="flex items-center gap-2">
                <IconLightbulb className="size-4.5 text-blue-30" />
                <div className="text-heading-small text-gray-50">캐치스턴트 AI에서 정확한 답변을 얻으려면</div>
              </div>
            </div>

            <div className="flex items-start gap-6 self-stretch">
              <button onClick={() => toggleCard('jira')} className="transition-transform hover:scale-[1.02]">
                <Image src={Jira} alt="jira" className="w-[368px] cursor-pointer" />
              </button>

              <button onClick={() => toggleCard('git')} className="transition-transform hover:scale-[1.02]">
                <Image src={Git} alt="git" className="w-[368px] cursor-pointer" />
              </button>
            </div>
          </div>

          {activeCard === 'jira' && <JiraGuideCard onClose={() => setActiveCard(null)} />}
          {activeCard === 'git' && <GithubGuideCard onClose={() => setActiveCard(null)} />}
        </div>
      </div>
    </div>
  );
}
