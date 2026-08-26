'use client';

// 홈(/) 본문 콘텐츠. `mode` 파라미터로 캐치스턴트 AI / 문서 탐색 두 섹션을 전환한다.
// ai 모드는 `q` 파라미터를 컴포저 입력 초기값으로 받는다.

import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useRouter, useSearchParams } from 'next/navigation';

import { ADMIN_GUIDE_STORAGE_KEY } from '@/features/home/constants/adminGuide';
import { FEATURE_UPDATE_NOTICE, FEATURE_UPDATE_NOTICE_ID } from '@/features/home/constants/featureUpdateNotice';
import { tipData } from '@/features/home/constants/questionTips';
import { USER_GUIDE_STORAGE_KEY } from '@/features/home/constants/userGuide';
import TopNavbar from '@/shared/components/layout/topNavbar/TopNavbar';
import { useQuestionHistoryGate } from '@/shared/hooks/query/useQuestionHistoryGate';
import { useSearchFilters } from '@/shared/hooks/query/useSearchFilters';
import { useSearchInput } from '@/shared/hooks/query/useSearchInput';
import { useEscapeKey } from '@/shared/hooks/useEscapeKey';
import useLocalStorage from '@/shared/hooks/useLocalStorage';
import { useOutsideClick } from '@/shared/hooks/useOutsideClick';
import { useServiceNoticeDismiss } from '@/shared/hooks/useServiceNoticeDismiss';
import { useUserStore } from '@/shared/store/userStore';

import AdminGuideModal from './AdminGuideModal';
import FeatureUpdateNoticeModal from './FeatureUpdateNoticeModal';
import HomeAiSection from './HomeAiSection';
import HomeDocsSection from './HomeDocsSection';
import ModePicker, { type HomeMode } from './ModePicker';
import UserGuideModal from './UserGuideModal';

type TopNavPageType = 'home' | 'docs';

function resolveTopNavPageType(mode: HomeMode): TopNavPageType {
  return mode === 'docs' ? 'docs' : 'home';
}

export default function HomeContent() {
  const user = useUserStore((state) => state.user);
  const router = useRouter();
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

  // 신규 기능 업데이트 공지. 가이드(admin/user)가 뜬 상태에서는 노출하지 않는다.
  const { isDismissed: noticeDismissed, dismiss: dismissNotice } = useServiceNoticeDismiss(FEATURE_UPDATE_NOTICE_ID);
  const [noticeClosed, setNoticeClosed] = useState(false);
  const showFeatureUpdate = !noticeDismissed && !noticeClosed && !showAdminGuide && !showUserGuide;

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const filters = useSearchFilters();
  const searchQuery = mode === 'ai' ? (searchParams.get('q') ?? '') : '';
  const input = useSearchInput({
    inputRef,
    selectedSources: filters.selectedSources,
    tipData,
    initialValue: searchQuery,
  });

  // 홈에 머문 채 `/?q=…`로 재진입하면 컴포저 입력을 그 값으로 맞춘다. 빈 q는 입력을 건드리지 않는다.
  const { setValue } = input;
  useEffect(() => {
    if (!searchQuery) return;
    setValue(searchQuery);
  }, [searchQuery, setValue]);

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
      <TopNavbar pageType={resolveTopNavPageType(mode)} />

      <div className="flex flex-col items-center pt-14 pb-6">
        <ModePicker mode={mode} />
      </div>

      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={mode}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18, ease: 'easeOut' }}
          className="flex w-full flex-col"
        >
          {mode === 'ai' ? (
            <HomeAiSection
              input={input}
              filters={filters}
              inputRef={inputRef}
              containerRef={containerRef}
              shouldShowNoHistoryBox={shouldShowNoHistoryBox}
              isNoHistoryExpanded={isNoHistoryExpanded}
              isHome
              userName={user?.name ?? ''}
            />
          ) : (
            <HomeDocsSection />
          )}
        </motion.div>
      </AnimatePresence>

      {showAdminGuide && <AdminGuideModal onDismiss={() => setAdminGuideDismissed(true)} />}
      {showUserGuide && <UserGuideModal onDismiss={() => setUserGuideDismissed(true)} />}
      {showFeatureUpdate && (
        <FeatureUpdateNoticeModal
          open
          onOpenChange={(next) => {
            if (!next) setNoticeClosed(true);
          }}
          onConfirm={() => router.replace(FEATURE_UPDATE_NOTICE.ctaHref)}
          onDismiss={dismissNotice}
        />
      )}
    </div>
  );
}
