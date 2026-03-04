'use client';

import { useRef, useState } from 'react';

import AdminGuideModal from '@/features/home/components/AdminGuideModal';
import HowToUse from '@/features/home/components/HowToUse';
import QuestionTips from '@/features/home/components/QuestionTips';
import UserGuideModal from '@/features/home/components/UserGuideModal';
import { ADMIN_GUIDE_STORAGE_KEY } from '@/features/home/constants/adminGuide';
import { USER_GUIDE_STORAGE_KEY } from '@/features/home/constants/userGuide';
import TopNavbar from '@/shared/components/layout/topNavbar/TopNavbar';
import QueryBox from '@/shared/components/query/QueryBox';
import { useQuestionHistoryGate } from '@/shared/hooks/query/useQuestionHistoryGate';
import { useSearchFilters } from '@/shared/hooks/query/useSearchFilters';
import { useSearchInput } from '@/shared/hooks/query/useSearchInput';
import { useEscapeKey } from '@/shared/hooks/useEscapeKey';
import useLocalStorage from '@/shared/hooks/useLocalStorage';
import { useOutsideClick } from '@/shared/hooks/useOutsideClick';
import { useUserStore } from '@/shared/store/userStore';

export default function Home() {
  const user = useUserStore((state) => state.user);
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
  const input = useSearchInput({ inputRef, selectedSources: filters.selectedSources });
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

  return (
    <div className={`bg-home-gradient flex flex-col ${input.isFocused ? 'h-full overflow-hidden' : ''}`}>
      <TopNavbar pageType="home" />

      {/* Query Section */}
      <div className="flex flex-col items-center gap-4 self-stretch pt-18 pb-18">
        {/* TEXT */}
        <div className="grid h-24 place-items-center">
          <div
            className={`flex flex-col items-center gap-3 transition-opacity duration-300 [grid-area:1/1] ${
              input.isFocused ? 'pointer-events-none opacity-0' : 'opacity-100'
            }`}
          >
            <h1 className="text-display-xlarge text-normal-normal">반갑습니다, {user?.name ?? ''}님!</h1>
            <p className="text-heading-large text-normal-alternative">
              무엇을 도와드릴까요? 필요한 업무정보를 찾아보세요.
            </p>
          </div>
          <div
            className={`flex flex-col items-center text-center transition-opacity duration-300 [grid-area:1/1] ${
              input.isFocused ? 'opacity-100' : 'pointer-events-none opacity-0'
            }`}
          >
            <h1 className="text-display-xlarge text-normal-normal">
              사내 AI 탐색으로
              <br />
              <span className="text-blue-50">필요한 업무 자료를 </span>
              바로 찾아보세요
            </h1>
          </div>
        </div>

        {/* Query Box */}
        <QueryBox
          containerRef={containerRef}
          inputRef={inputRef}
          input={input}
          filters={filters}
          variant={shouldShowNoHistoryBox ? 'no-history' : 'default'}
          noHistoryExpanded={isNoHistoryExpanded || input.isFocused}
          highlightBracketPlaceholders
        />
      </div>

      <div
        className={`flex flex-col items-center gap-16 px-16 pt-10 pb-30 transition-all duration-300 ${
          input.isFocused ? 'pointer-events-none translate-y-4 opacity-0' : 'opacity-100'
        }`}
      >
        <QuestionTips
          onTipClick={(query) => {
            input.setValue(query);
            input.setIsFocused(true);
            inputRef.current?.focus();
          }}
        />
        <HowToUse />
      </div>

      {showAdminGuide && <AdminGuideModal onDismiss={() => setAdminGuideDismissed(true)} />}
      {showUserGuide && <UserGuideModal onDismiss={() => setUserGuideDismissed(true)} />}
    </div>
  );
}
