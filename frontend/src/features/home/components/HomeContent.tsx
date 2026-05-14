'use client';

// 홈(/) 페이지와 search(/search) 페이지가 공유하는 본문 콘텐츠.
// 두 라우트는 단지 경로만 다르고 화면 구성은 동일하다 — TopNavbar 라벨만 path/mode에 따라 분기.

import { useRef, useState } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';

import type { DocsSource } from '@/shared/types/source';

import { ADMIN_GUIDE_STORAGE_KEY } from '@/features/home/constants/adminGuide';
import { tipData } from '@/features/home/constants/questionTips';
import { USER_GUIDE_STORAGE_KEY } from '@/features/home/constants/userGuide';
import TopNavbar from '@/shared/components/layout/topNavbar/TopNavbar';
import QueryBox from '@/shared/components/query/QueryBox';
import SourceChipsRow from '@/shared/components/SourceChipsRow';
import { useQuestionHistoryGate } from '@/shared/hooks/query/useQuestionHistoryGate';
import { useSearchFilters } from '@/shared/hooks/query/useSearchFilters';
import { useSearchInput } from '@/shared/hooks/query/useSearchInput';
import { useEscapeKey } from '@/shared/hooks/useEscapeKey';
import useLocalStorage from '@/shared/hooks/useLocalStorage';
import { useOutsideClick } from '@/shared/hooks/useOutsideClick';
import { useUserStore } from '@/shared/store/userStore';

import AdminGuideModal from './AdminGuideModal';
import DocsQueryBox from './DocsQueryBox';
import DocsSearchHistorySection from './DocsSearchHistorySection';
import HeroText from './HeroText';
import HowToUse from './HowToUse';
import ModePicker, { type HomeMode } from './ModePicker';
import PromptChips from './PromptChips';
import QuestionTips from './QuestionTips';
import UserGuideModal from './UserGuideModal';

type TopNavPageType = 'home' | 'search' | 'docs';

function resolveTopNavPageType(pathname: string, mode: HomeMode): TopNavPageType {
  if (mode === 'docs') return 'docs';
  if (pathname === '/search') return 'search';
  return 'home';
}

export default function HomeContent() {
  const user = useUserStore((state) => state.user);
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const mode: HomeMode = searchParams.get('mode') === 'docs' ? 'docs' : 'ai';

  const [adminGuideDismissed, setAdminGuideDismissed] = useLocalStorage({
    key: ADMIN_GUIDE_STORAGE_KEY,
    initialValue: false,
  });
  const [userGuideDismissed, setUserGuideDismissed] = useLocalStorage({
    key: USER_GUIDE_STORAGE_KEY,
    initialValue: false,
  });
  const showAdminGuide = user?.role === 'admin' && !adminGuideDismissed;
  const showUserGuide = user?.role !== 'admin' && !userGuideDismissed;

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const filters = useSearchFilters();
  const input = useSearchInput({ inputRef, selectedSources: filters.selectedSources, tipData });
  const { shouldShowNoHistoryBox } = useQuestionHistoryGate();
  const [isNoHistoryExpanded, setIsNoHistoryExpanded] = useState(true);
  const [docsSources, setDocsSources] = useState<DocsSource[]>([]);

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

  return (
    <div className={`bg-home-gradient flex min-h-full flex-col ${input.isFocused ? 'h-full overflow-y-auto' : ''}`}>
      <TopNavbar pageType={resolveTopNavPageType(pathname, mode)} />

      {/* Query Section */}
      <div className="flex flex-col items-center gap-6 self-stretch py-18">
        <ModePicker mode={mode} />

        <div className="grid h-24 place-items-center">
          <HeroText mode={mode} isFocused={input.isFocused} />
        </div>

        <div ref={containerRef} className="flex flex-col items-center gap-4">
          {mode === 'ai' ? (
            <>
              <QueryBox
                inputRef={inputRef}
                input={input}
                filters={filters}
                variant={shouldShowNoHistoryBox ? 'no-history' : 'default'}
                noHistoryExpanded={isNoHistoryExpanded || input.isFocused}
                tipData={tipData}
              />
              {input.isFocused && (
                <PromptChips
                  selectedIndex={input.selectedTipIndex}
                  onChipClick={(index) => {
                    input.resetTemplateFields();
                    input.setIsFromTemplate(true);
                    input.setSelectedTipIndex(index);
                  }}
                />
              )}
            </>
          ) : (
            <>
              <DocsQueryBox selectedSources={docsSources} />
              <SourceChipsRow
                className="w-222"
                selectedSources={docsSources}
                onToggle={setDocsSources}
              />
            </>
          )}
        </div>
      </div>

      {mode === 'ai' && (
        <div
          className={`flex flex-col items-center gap-16 px-16 pt-4 pb-30 transition-[opacity,transform] duration-300 ${
            input.isFocused ? 'pointer-events-none h-0 translate-y-4 overflow-hidden opacity-0' : 'opacity-100'
          }`}
        >
          <QuestionTips
            onTipClick={(index) => {
              input.resetTemplateFields();
              input.setIsFromTemplate(true);
              input.setSelectedTipIndex(index);
              input.setIsFocused(true);
            }}
          />
          <HowToUse />
        </div>
      )}

      {mode === 'docs' && <DocsSearchHistorySection />}

      {showAdminGuide && <AdminGuideModal onDismiss={() => setAdminGuideDismissed(true)} />}
      {showUserGuide && <UserGuideModal onDismiss={() => setUserGuideDismissed(true)} />}
    </div>
  );
}
