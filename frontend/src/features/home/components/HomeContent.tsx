'use client';

// 홈(/) 페이지와 search(/search) 페이지가 공유하는 본문 콘텐츠.
// 두 라우트는 단지 경로만 다르고 화면 구성은 동일하다 — TopNavbar 라벨만 path/mode에 따라 분기.
// mode 분기는 두 section 컴포넌트로 위임 + 다음 task에서 AnimatePresence fade 적용.

import { usePathname, useSearchParams } from 'next/navigation';
import { useRef, useState } from 'react';

import { ADMIN_GUIDE_STORAGE_KEY } from '@/features/home/constants/adminGuide';
import { tipData } from '@/features/home/constants/questionTips';
import { USER_GUIDE_STORAGE_KEY } from '@/features/home/constants/userGuide';
import TopNavbar from '@/shared/components/layout/topNavbar/TopNavbar';
import { useQuestionHistoryGate } from '@/shared/hooks/query/useQuestionHistoryGate';
import { useSearchFilters } from '@/shared/hooks/query/useSearchFilters';
import { useSearchInput } from '@/shared/hooks/query/useSearchInput';
import { useEscapeKey } from '@/shared/hooks/useEscapeKey';
import useLocalStorage from '@/shared/hooks/useLocalStorage';
import { useOutsideClick } from '@/shared/hooks/useOutsideClick';
import { useUserStore } from '@/shared/store/userStore';

import AdminGuideModal from './AdminGuideModal';
import HomeAiSection from './HomeAiSection';
import HomeDocsSection from './HomeDocsSection';
import ModePicker, { type HomeMode } from './ModePicker';
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

  // QueryBox 포커스 해제 + no-history 패널 닫기 공통 로직 (ai 모드만 영향).
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

      <div className="flex flex-col items-center pt-18 pb-6">
        <ModePicker mode={mode} />
      </div>

      {mode === 'ai' ? (
        <HomeAiSection
          input={input}
          filters={filters}
          inputRef={inputRef}
          containerRef={containerRef}
          shouldShowNoHistoryBox={shouldShowNoHistoryBox}
          isNoHistoryExpanded={isNoHistoryExpanded}
        />
      ) : (
        <HomeDocsSection />
      )}

      {showAdminGuide && <AdminGuideModal onDismiss={() => setAdminGuideDismissed(true)} />}
      {showUserGuide && <UserGuideModal onDismiss={() => setUserGuideDismissed(true)} />}
    </div>
  );
}
