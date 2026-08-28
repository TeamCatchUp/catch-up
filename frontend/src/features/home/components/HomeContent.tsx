'use client';

// 홈(/) 본문. 컴포저 안의 모드 토글이 `mode` 파라미터를 바꾸고, 그 아래 블록이 함께 전환된다.
// ai 모드는 `q` 파라미터를 컴포저 입력 초기값으로 받는다.

import { useEffect, useRef, useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { AnimatePresence, motion } from 'motion/react';
import { useRouter, useSearchParams } from 'next/navigation';

import { ADMIN_GUIDE_STORAGE_KEY } from '@/features/home/constants/adminGuide';
import { FEATURE_UPDATE_NOTICE, FEATURE_UPDATE_NOTICE_ID } from '@/features/home/constants/featureUpdateNotice';
import { TEMPLATE_ICONS, tipData } from '@/features/home/constants/questionTips';
import { USER_GUIDE_STORAGE_KEY } from '@/features/home/constants/userGuide';
import TopNavbar from '@/shared/components/layout/topNavbar/TopNavbar';
import { useSearchFilters } from '@/shared/hooks/query/useSearchFilters';
import { useSearchInput } from '@/shared/hooks/query/useSearchInput';
import useLocalStorage from '@/shared/hooks/useLocalStorage';
import { useServiceNoticeDismiss } from '@/shared/hooks/useServiceNoticeDismiss';
import { useUserStore } from '@/shared/store/userStore';
import type { DocsSource } from '@/shared/types/source';
import { buildHybridSearchUrl } from '@/shared/utils/buildHybridSearchUrl';

import AdminGuideModal from './AdminGuideModal';
import type { HomeMode } from './ComposerModeToggle';
import DocsSearchHistorySection from './DocsSearchHistorySection';
import FeatureUpdateNoticeModal from './FeatureUpdateNoticeModal';
import HeroText from './HeroText';
import HomeComposer from './HomeComposer';
import QuickTemplateList from './QuickTemplateList';
import UserGuideModal from './UserGuideModal';

const FADE = { duration: 0.18, ease: 'easeOut' } as const;

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
  // 템플릿이 꽂혀 있으면 함께 풀어야 새 질의가 입력창에 보인다.
  const { setValue, setIsFromTemplate, setSelectedTipIndex, resetTemplateFields } = input;
  useEffect(() => {
    if (!searchQuery) return;
    resetTemplateFields();
    setIsFromTemplate(false);
    setSelectedTipIndex(null);
    setValue(searchQuery);
  }, [searchQuery, setValue, setIsFromTemplate, setSelectedTipIndex, resetTemplateFields]);

  // 문서 탐색 필터는 모드를 오가도 유지된다.
  const [docsSources, setDocsSources] = useState<DocsSource[]>([]);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(undefined);
  const [smartFilter, setSmartFilter] = useState(true);

  const handleModeChange = (next: HomeMode) => {
    if (next === mode) return;
    const params = new URLSearchParams(searchParams.toString());
    if (next === 'docs') params.set('mode', 'docs');
    else params.delete('mode');
    const query = params.toString();
    router.replace(query ? `/?${query}` : '/');
  };

  const handleDocsSubmit = () => {
    const url = buildHybridSearchUrl({ query: input.value, sources: docsSources, dateRange, smartFilter });
    if (url) router.push(url);
  };

  // 포커스는 TemplateInput이 첫 빈칸에 준다 — 여기서 잡으면 곧 사라질 textarea를 잡는다.
  const handleTemplateClick = (index: number) => {
    input.resetTemplateFields();
    input.setIsFromTemplate(true);
    input.setSelectedTipIndex(index);
  };

  const selectedTipIndex = input.isFromTemplate ? input.selectedTipIndex : null;
  const selectedTemplateLabel = selectedTipIndex !== null ? (tipData[selectedTipIndex]?.chipLabel ?? null) : null;
  const SelectedTemplateIcon = selectedTipIndex !== null ? (TEMPLATE_ICONS[selectedTipIndex] ?? null) : null;

  const handleTemplateRemove = () => {
    input.resetTemplateFields();
    input.setIsFromTemplate(false);
    input.setSelectedTipIndex(null);
  };

  return (
    <div className="bg-home-gradient flex min-h-full flex-col overflow-y-auto">
      <TopNavbar pageType="home" />

      <div className="flex flex-col items-center gap-9 px-16 pt-30 pb-30">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={mode}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={FADE}
          >
            <HeroText mode={mode} userName={user?.name ?? ''} />
          </motion.div>
        </AnimatePresence>

        <HomeComposer
          mode={mode}
          onModeChange={handleModeChange}
          input={input}
          filters={filters}
          inputRef={inputRef}
          docsSources={docsSources}
          onDocsSourcesChange={setDocsSources}
          dateRange={dateRange}
          onDateRangeChange={setDateRange}
          smartFilter={smartFilter}
          onSmartFilterChange={setSmartFilter}
          onAiSubmit={input.handleSubmit}
          onDocsSubmit={handleDocsSubmit}
          tipData={tipData}
          selectedTemplateLabel={selectedTemplateLabel}
          TemplateIcon={SelectedTemplateIcon}
          onTemplateRemove={handleTemplateRemove}
        />

        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={mode}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={FADE}
            className="w-190"
          >
            {mode === 'ai' ? (
              <QuickTemplateList onTemplateClick={handleTemplateClick} />
            ) : (
              <DocsSearchHistorySection selectedSources={docsSources} dateRange={dateRange} smartFilter={smartFilter} />
            )}
          </motion.div>
        </AnimatePresence>
      </div>

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
